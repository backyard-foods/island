import time
from escpos.printer import Usb
from escpos.exceptions import DeviceNotFoundError
import threading
import json
import os
from utils import format_string
from cachetools import TTLCache, cached

# ~270x50 PNG, black on transparent
LOGO_PATH = "receipt-logo.png"

LOGO_FRAGMENT_HEIGHT = 100
LOGO_SLEEP_BETWEEN_FRAGMENTS_MS = 0
SLEEP_BETWEEN_SEGMENTS_MS = 50

# EU-m30 (Kiosk)Settings
MODEL_KIOSK = 0x0e2e

# TM-T88IV (Traditional) Settings
MODEL_TRADITIONAL = 0x0202

# Shared settings
MAKE = 0x04b8 # Epson
PROFILE = "TM-T88IV"
LOGO_FRAGMENT_HEIGHT = 2
LOGO_SLEEP_BETWEEN_FRAGMENTS_MS = 50
SLEEP_BETWEEN_SEGMENTS_MS = 50
PRINT_COOLDOWN = 4
POLL_COOLDOWN = 1
TIMEOUT = 30
TRANSMIT_READ_DELAY_MS = 300
CONFIGURATION_SLEEP_TIME = 10

# EU-m30 printer status constants
TRANSMIT_STATUS = b'\x10\x04'
TRANSMIT_PRINTER_STATUS = TRANSMIT_STATUS + b'\x01'
VALID_PRINTER_STATUSES = [
    0b00010110,
    0b00011110,
    0b00110110,
    0b00111110,
    0b01010110,
    0b01011110,
    0b01110110,
    0b01111110
]
OFFLINE_MASK = 0b00011110
WAITING_FOR_RECOVERY_MASK = 0b00110110
PAPER_FEED_BUTTON_MASK = 0b01010110

TRANSMIT_OFFLINE_CAUSE = TRANSMIT_STATUS + b'\x02'
OFFLINE_COVER_OPEN_MASK = 0b00010110
OFFLINE_PAPER_FEED_BUTTON_MASK = 0b00011010
OFFLINE_PAPER_OUT_MASK = 0b00110010
OFFLINE_ERROR_MASK = 0b01010010

TRANSMIT_ERROR_CAUSE = TRANSMIT_STATUS + b'\x03'
ERROR_RECOVERABLE_MASK = 0b00010110
ERROR_AUTOCUTTER_MASK = 0b00011010
ERROR_UNRECOVERABLE_MASK = 0b00110010
ERROR_AUTORECOVERABLE_MASK = 0b01010010

TRANSMIT_PAPER_STATUS = TRANSMIT_STATUS + b'\x04'
VALID_PAPER_STATUSES = [0b00010010, 0b01110010, 0b00011110, 0b01111110]
PAPER_OUT_MASK = 0b01110010
PAPER_LOW_MASK = 0b00011110

class ReceiptPrinterManager:
    def __init__(self):
        kiosk = os.environ.get("RECEIPT_PRINTER_KIOSK", "true").lower() == "true"
        if kiosk:
            model = MODEL_KIOSK
        else:
            model = MODEL_TRADITIONAL
        self.printer = Usb(idVendor=MAKE, idProduct=model, usb_args={}, timeout=TIMEOUT, profile=PROFILE)
        self.cooldown = PRINT_COOLDOWN
        self.last_request_time = 0
        self.lock = threading.Lock()
        self.last_status = None
        self.get_status()

    def configure_printer(self, fast=False, high_density=True):
        print("Configuring printer")
        try:

            gs = b'\x1D' # prefix for GS commands
            e_command = b'\x28\x45'  # prefix for GS ( E commands

            # Function 1 - Open User Setting Mode 
            pL = b'\x03' # data length low byte
            pH = b'\x00' # data length high byte
            fn = b'\x01' # function code 1
            d1 = b'\x49' # data 1: character "I"
            d2 = b'\x4E' # data 2: character "N"
            print(f"Sending 'Open User Setting' command: {gs + e_command + pL + pH + fn + d1 + d2}")
            self.printer._raw(gs + e_command + pL + pH + fn + d1 + d2)
            self.clear_receipt_data_buffer()

            # Function 5 - 5: Set Print Density
            pL = b'\x04' # data length low byte
            pH = b'\x00' # data length high byte
            fn = b'\x05' # function code 5
            a = b'\x05' # print density setting (5)
            nL = b'\x00' # 0 for normal (100%), 6 for high density (130%)
            if high_density:
                nL = b'\x06'
            nH = b'\x00' # high bit (unused)
            print(f"Sending 'Set Print Density' command: {gs + e_command + pL + pH + fn + a + nL + nH}")
            self.printer._raw(gs + e_command + pL + pH + fn + a + nL + nH)
            self.clear_receipt_data_buffer()

            # Function 5 - 6: Set Print Speed
            pL = b'\x04' # data length low byte
            pH = b'\x00' # data length high byte
            fn = b'\x05' # function code 5
            a = b'\x06' # print speed setting (6)
            nL = b'\x08' # 1-13 for level 1 to level 13
            if fast:
                nL = b'\x0C'
            nH = b'\x00' # high bit (unused)
            print(f"Sending 'Set Print Speed' command: {gs + e_command + pL + pH + fn + a + nL + nH}")
            self.printer._raw(gs + e_command + pL + pH + fn + a + nL + nH)
            self.clear_receipt_data_buffer()

            # Function 2 - Close User Setting Mode 
            pL = b'\x04' # data length low byte
            pH = b'\x00' # data length high byte
            fn = b'\x02' # function code 2
            d1 = b'\x4F' # data 1: character "O"
            d2 = b'\x55' # data 2: character "U"
            d3 = b'\x54' # data 3: character "T"
            print(f"Sending 'Close User Setting' command: {gs + e_command + pL + pH + fn + d1 + d2 + d3}")
            self.printer._raw(gs + e_command + pL + pH + fn + d1 + d2 + d3)
            self.clear_receipt_data_buffer()

            self.printer.close()

            for i in range(CONFIGURATION_SLEEP_TIME):
                print(f"Waiting... {i+1}/{CONFIGURATION_SLEEP_TIME} seconds")
                time.sleep(1)
            
            return True
        except Exception as e:
            print(f"Configuration error: {str(e)}")
            return False   

    def get_printer_status(self):
        print(f"Getting printer status")
        self.printer.open()
        self.printer._raw(TRANSMIT_PRINTER_STATUS)
        time.sleep(TRANSMIT_READ_DELAY_MS/1000)
        printer_status_raw = self.printer._read()
        self.printer.close()

        #print(f"Printer status raw: {printer_status_raw}")
        printer_status_int = int.from_bytes(printer_status_raw, byteorder='big')
        #print(f"Printer status int: {printer_status_int}")
        printer_status_bits = bin(printer_status_int)[2:].zfill(8)
        #print(f"Printer status bits: {printer_status_bits}")

        valid_printer_status = printer_status_int in VALID_PRINTER_STATUSES
        offline = valid_printer_status and (printer_status_int & OFFLINE_MASK) == OFFLINE_MASK
        waiting_for_recovery = valid_printer_status and (printer_status_int & WAITING_FOR_RECOVERY_MASK) == WAITING_FOR_RECOVERY_MASK
        paper_feed_button = valid_printer_status and (printer_status_int & PAPER_FEED_BUTTON_MASK) == PAPER_FEED_BUTTON_MASK

        #print(f"Valid printer status: {valid_printer_status}")
        #print(f"Offline: {offline}")
        #print(f"Waiting for recovery: {waiting_for_recovery}")
        #print(f"Paper feed button: {paper_feed_button}")
        return {
            'query_error': not valid_printer_status,
            'offline': offline,
            'waiting_for_recovery': waiting_for_recovery,
            'paper_feed_button': paper_feed_button
        }
    
    def get_offline_cause(self):
        print(f"Getting offline cause")
        self.printer.open()
        self.printer._raw(TRANSMIT_OFFLINE_CAUSE)
        time.sleep(TRANSMIT_READ_DELAY_MS/1000)
        offline_cause_raw = self.printer._read()
        self.printer.close()

        print(f"Offline cause raw: {offline_cause_raw}")
        offline_cause_int = int.from_bytes(offline_cause_raw, byteorder='big')
        print(f"Offline cause int: {offline_cause_int}")
        offline_cause_bits = bin(offline_cause_int)[2:].zfill(8)
        print(f"Offline cause bits: {offline_cause_bits}")

        cover_open = offline_cause_int & OFFLINE_COVER_OPEN_MASK == OFFLINE_COVER_OPEN_MASK
        paper_feed_button = offline_cause_int & OFFLINE_PAPER_FEED_BUTTON_MASK == OFFLINE_PAPER_FEED_BUTTON_MASK
        paper_out = offline_cause_int & OFFLINE_PAPER_OUT_MASK == OFFLINE_PAPER_OUT_MASK
        error = offline_cause_int & OFFLINE_ERROR_MASK == OFFLINE_ERROR_MASK

        valid_offline_cause = cover_open or paper_feed_button or paper_out or error

        print(f"Valid offline cause: {valid_offline_cause}")
        print(f"Cover open: {cover_open}")
        print(f"Paper feed button: {paper_feed_button}")
        print(f"Paper out: {paper_out}")
        print(f"Error: {error}")
        return {
            'query_error': not valid_offline_cause,
            'cover_open': cover_open,
            'paper_feed_button': paper_feed_button,
            'paper_out': paper_out,
            'error': error
        }
    
    def get_error_cause(self):
        print(f"Getting error cause")
        self.printer.open()
        self.printer._raw(TRANSMIT_ERROR_CAUSE)
        time.sleep(TRANSMIT_READ_DELAY_MS/1000)
        error_cause_raw = self.printer._read()
        self.printer.close()

        print(f"Error cause raw: {error_cause_raw}")
        error_cause_int = int.from_bytes(error_cause_raw, byteorder='big')
        print(f"Error cause int: {error_cause_int}")
        error_cause_bits = bin(error_cause_int)[2:].zfill(8)
        print(f"Error cause bits: {error_cause_bits}")

        recoverable = error_cause_int & ERROR_RECOVERABLE_MASK == ERROR_RECOVERABLE_MASK
        autocutter = error_cause_int & ERROR_AUTOCUTTER_MASK == ERROR_AUTOCUTTER_MASK
        unrecoverable = error_cause_int & ERROR_UNRECOVERABLE_MASK == ERROR_UNRECOVERABLE_MASK
        autorecoverable = error_cause_int & ERROR_AUTORECOVERABLE_MASK == ERROR_AUTORECOVERABLE_MASK

        valid_error_cause = recoverable or autocutter or unrecoverable or autorecoverable

        print(f"Valid error cause: {valid_error_cause}")
        print(f"Recoverable: {recoverable}")
        print(f"Autocutter: {autocutter}")
        print(f"Unrecoverable: {unrecoverable}")
        print(f"Autorecoverable: {autorecoverable}")
        return {
            'query_error': not valid_error_cause,
            'recoverable': recoverable,
            'autocutter': autocutter,
            'unrecoverable': unrecoverable,
            'autorecoverable': autorecoverable
        }

    def get_paper_status(self):
        print(f"Getting paper status")
        self.printer.open()
        self.printer._raw(TRANSMIT_PAPER_STATUS)
        time.sleep(TRANSMIT_READ_DELAY_MS/1000)
        paper_status_raw = self.printer._read()
        self.printer.close()

        #print(f"Paper status raw: {paper_status_raw}")
        paper_status_int = int.from_bytes(paper_status_raw, byteorder='big')
        #print(f"Paper status int: {paper_status_int}")
        paper_status_bits = bin(paper_status_int)[2:].zfill(8)
        #print(f"Paper status bits: {paper_status_bits}")

        valid_paper_status = paper_status_int in VALID_PAPER_STATUSES
        paper_out = valid_paper_status and (paper_status_int & PAPER_OUT_MASK) == PAPER_OUT_MASK
        paper_low = valid_paper_status and not paper_out and (paper_status_int & PAPER_LOW_MASK) == PAPER_LOW_MASK

        #print(f"Valid paper status: {valid_paper_status}")
        #print(f"Paper out: {paper_out}")
        #print(f"Paper low: {paper_low}")
        return {
            'query_error': not valid_paper_status,
            'paper_out': paper_out,
            'paper_low': paper_low
        }

    def get_status(self):
        with self.lock:
            self.throttle(printing=False)
            status = "unknown"
            reason = None
            try:
                printer_status = self.get_printer_status()
                print(f"Printer status: {printer_status}")

                paper_status = self.get_paper_status()
                print(f"Paper status: {paper_status}")

                if printer_status['query_error']:
                    status = "unknown"
                    reason = "invalid printer status"
                elif paper_status['query_error']:
                    status = "unknown"
                    reason = "invalid paper status"
                elif paper_status['paper_out']:
                    status = "no_paper"
                elif not printer_status['offline']:
                    if paper_status['paper_low']:
                        status = "low_paper"
                    else:
                        status = "ready"
                else:
                    status = "printer_offline"

                    offline_cause = self.get_offline_cause()
                    print(f"Offline cause: {offline_cause}")
                    
                    if not offline_cause['query_error']:
                        if offline_cause['cover_open']:
                            reason = "cover_open"
                        elif offline_cause['paper_feed_button']:
                            reason = "paper_feed_button"
                        elif offline_cause['paper_out']:
                            reason = "paper_out"
                        elif offline_cause['error']:
                            error_cause = self.get_error_cause()
                            print(f"Error cause: {error_cause}")
                            status = "error"
                            if not error_cause['query_error']:
                                if error_cause['autorecoverable']:
                                    reason = "autorecoverable"
                                elif error_cause['unrecoverable']:
                                    reason = "unrecoverable"
                                elif error_cause['recoverable']:
                                    reason = "recoverable"
                                elif error_cause['autocutter']:
                                    reason = "autocutter"
            except DeviceNotFoundError as e:
                print(f"Printer not found: {str(e)}")
                status = "not_found"
                reason = str(e)
            except Exception as e:
                print(f"Status check error: {str(e)}")
                status = "unknown"
                reason = f"exception: {str(e)}"
            finally:
                self.last_status = status
                self.printer.close()
            return {
                "status": status,
                "reason": reason
            }

    def throttle(self, printing=True):
        current_time = time.time()
        elapsed_time = current_time - self.last_request_time
        if elapsed_time < self.cooldown:
            time.sleep(self.cooldown - elapsed_time)
            print(f"Throttled for {self.cooldown - elapsed_time} seconds")
        self.last_request_time = time.time()
        if printing:
            self.cooldown = PRINT_COOLDOWN
        else:
            self.cooldown = POLL_COOLDOWN

    @cached(cache=TTLCache(maxsize=100, ttl=1 * 60))
    def print_receipt(self, order, upcs, details, message, wait):
        print(f"Printing receipt for order: {order}, upcs: {upcs}, details: {details}, message: {message}, wait: {wait}")
        with self.lock:
            self.throttle()

            if self.last_status != "ready" and self.last_status != "low_paper":
                print(f"Printer not ready: {self.last_status}")
                self.printer.close()
                return False
            try:
                self.start_print_job()
                instructions = "PAY AT REGISTER"

                self.print_logo()
                self.print_heading(order)
                self.print_message(instructions, bold=True)
                self.print_details(details)
                
                if(upcs):
                    try:
                        upcs = json.loads(upcs)
                    except json.JSONDecodeError:
                        print(f"Error: Invalid UPC format. Received: {upcs}")
                        upcs = []
                    for upc in upcs:
                        self.print_barcode(upc)
                
                self.print_message(message)
                
                self.end_print_job()
                
                return True
            
            except Exception as e:
                print(f"Print error: {str(e)}")
                self.end_print_job()
                return False
            
    def start_print_job(self):
        self.printer.open()
        self.printer.set_sleep_in_fragment(LOGO_SLEEP_BETWEEN_FRAGMENTS_MS)
        self.printer.set(align='center', normal_textsize=True, flip=False)
        print(f"Printing")

    def end_print_job(self):
        self.printer.cut()
        self.printer.close()

    def print_logo(self):
        self.printer.image(LOGO_PATH,
                           high_density_vertical=True, 
                           high_density_horizontal=True, 
                           impl='bitImageRaster', 
                           fragment_height=LOGO_FRAGMENT_HEIGHT, 
                           center=False)
        self.clear_receipt_data_buffer()

    def print_heading(self, order):
        if order:
            print(f"Printing heading")
            self.printer.ln(1)
            self.printer.set(align='center', double_height=True, double_width=True, bold=True, density=3)
            self.printer.text(format_string(f"{str(order).title()}", double_size=True, flip=False))
            self.printer.set(align='center', normal_textsize=True, flip=False)
            self.clear_receipt_data_buffer()
        else:  
            print(f"No order provided, skipping heading")

    def print_details(self, details):
        if details:
            print(f"Printing details")
            self.printer.ln(2)
            self.printer.set(align='center', normal_textsize=True)
            self.printer.text(format_string(details, double_size=False, flip=False))
            self.clear_receipt_data_buffer()
        else:
            print(f"No details provided, skipping details")

    def print_barcode(self, upc):
        if upc:
            print(f"Printing barcode")
            upc_str = str(upc)

            if not upc_str.isdigit() or len(upc_str) != 12:
                print(f"Error: Invalid UPC format. Received: {upc}")
                self.print_message("Invalid UPC")
                return
        
            self.printer.ln(2)
            self.printer.barcode(upc_str, 'UPC-A', 64, 2, '', 'A', True, 'B')
            self.clear_receipt_data_buffer()
        else:
            print(f"No UPC provided, skipping barcode")

    def print_message(self, message, bold=False):
        if message:
            print(f"Printing message")
            self.printer.ln(2)
            self.printer.set(align='center', normal_textsize=True, bold=bold)
            self.printer.text(format_string(message, double_size=False, flip=False))
            if bold: 
                self.printer.set(align='center', normal_textsize=True, bold=False)
            self.clear_receipt_data_buffer()
        else:
            print(f"No message provided, skipping message")
    
    def clear_receipt_data_buffer(self):
        time.sleep(SLEEP_BETWEEN_SEGMENTS_MS/1000)

    def reload_paper(self):
        with self.lock:
            self.throttle()
            try:
                self.printer.open()
                self.printer.ln(12)
                self.printer.text("RELOADING PAPER")
                self.printer.ln(12)
                self.printer.cut()
                self.printer.close()
            except Exception as e:
                print(f"Reload paper error: {str(e)}")
                return False
            return True
