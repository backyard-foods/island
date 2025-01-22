import time
from escpos.printer import Usb
from escpos.constants import QR_ECLEVEL_M
from escpos.exceptions import DeviceNotFoundError
import threading
import json
from utils import format_string

FEEDBACK_URL = "https://goodbear.co/feedback"
# ~270x50 PNG, black on transparent
LOGO_PATH = "receipt-logo.png"

LOGO_FRAGMENT_HEIGHT = 20
LOGO_SLEEP_BETWEEN_FRAGMENTS_MS = 0
SLEEP_BETWEEN_SEGMENTS_MS = 50

# TM-L00 printer settings
MAKE = 0x04b8
MODEL = 0x0e31
PROFILE = "TM-L90"  # Wrong profile for the TM-L100, but no issues so far
PRINT_COOLDOWN = 4
POLL_COOLDOWN = 2
TIMEOUT = 30
TRANSMIT_READ_DELAY_MS = 100
CONFIGURATION_SLEEP_TIME = 10

# TM-L00 printer status constants
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
VALID_PAPER_STATUSES = [0b00010010, 0b01110010]
PAPER_OUT_MASK = 0b01110010

class LabelPrinterManager:
    def __init__(self):
        self.printer = Usb(idVendor=MAKE, idProduct=MODEL, usb_args={}, timeout=TIMEOUT, profile=PROFILE)
        self.cooldown = PRINT_COOLDOWN
        self.last_request_time = 0
        self.lock = threading.Lock()
        self.last_status = None
        self.get_status()

    def configure_printer(self, buzzer=False, paper_removal_standby=False):
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
            self.clear_label_data_buffer()

            # Function 5 - 119: Set Buzzer Mode
            pL = b'\x04' # data length low byte
            pH = b'\x00' # data length high byte
            fn = b'\x05' # function code 5
            a = b'\x77' # buzzer setting (119)
            nL = b'\x00' # 0 for off, 1 for external, 2 for internal
            if buzzer:
                nL = b'\x02'
            nH = b'\x00' # high bit (unused)
            print(f"Sending 'Set Buzzer Mode' command: {gs + e_command + pL + pH + fn + a + nL + nH}")
            self.printer._raw(gs + e_command + pL + pH + fn + a + nL + nH)
            self.clear_label_data_buffer()

            # Function 5 - 14: Turn off paper removal standby
            pL = b'\x04' # data length low byte
            pH = b'\x00' # data length high byte
            fn = b'\x05' # function code 5
            a = b'\x0E' # buzzer setting (14)
            nL = b'\x00' # 0 (x00) for off, 64 (x40) for on
            if paper_removal_standby:
                nL = b'\x40'
            nH = b'\x00' # high bit (unused)
            print(f"Sending 'Turn off paper removal standby' command: {gs + e_command + pL + pH + fn + a + nL + nH}")
            self.printer._raw(gs + e_command + pL + pH + fn + a + nL + nH)
            self.clear_label_data_buffer()

            # Function 2 - Close User Setting Mode 
            pL = b'\x04' # data length low byte
            pH = b'\x00' # data length high byte
            fn = b'\x02' # function code 2
            d1 = b'\x4F' # data 1: character "O"
            d2 = b'\x55' # data 2: character "U"
            d3 = b'\x54' # data 3: character "T"
            print(f"Sending 'Close User Setting' command: {gs + e_command + pL + pH + fn + d1 + d2 + d3}")
            self.printer._raw(gs + e_command + pL + pH + fn + d1 + d2 + d3)
            self.clear_label_data_buffer()

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

        valid_paper_status = paper_status_int in VALID_PAPER_STATUSES
        paper_out = valid_paper_status and (paper_status_int & PAPER_OUT_MASK) == PAPER_OUT_MASK

        #print(f"Valid paper status: {valid_paper_status}")
        #print(f"Paper out: {paper_out}")
        return {
            'query_error': not valid_paper_status,
            'paper_out': paper_out
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

    def print_label(self, order, item, upcs, item_number, item_total, fulfillment=None, paid=False):
        with self.lock:
            print(f"acquired lock")
            self.throttle()
            if self.last_status != "ready":
                print(f"Printer not ready: {self.last_status}")
                self.printer.close()
                return False
            try:
                self.start_print_job()
                self.print_logo()

                if(order):
                    self.print_heading(order)

                if(item):
                    try:
                        if(int(item_total) > 1 and int(item_number) > 0):
                            self.print_details(item, item_number, item_total)
                        else:
                            self.print_details(item)
                    except ValueError:
                        self.print_details(item)
                        print(f"Invalid item_total value: {item_total}")
                    finally:
                        self.print_gap()

                if(upcs):
                    try:
                        upcs = json.loads(upcs)
                    except json.JSONDecodeError:
                        print(f"Error: Invalid UPC format. Received: {upcs}")
                        upcs = []

                if fulfillment and item and (len(upcs) <= 1 or paid):
                    self.print_qr(fulfillment, item)
                
                if paid:
                    self.print_paid()
                else:
                    for i in range(len(upcs)):
                        self.print_barcode(upcs[i])
                        if i < len(upcs) - 1:
                            self.print_gap()
                            
                self.end_print_job()
                
                return True
            
            except Exception as e:
                print(f"Print error: {str(e)}")
                self.end_print_job()
                return False
            
    def print_text(self, text):
        print(f"Printing text: {text}")
        with self.lock:
            self.throttle()
            try:
                self.printer.open()
                self.printer.ln(4)
                self.printer.set(align='center', double_height=True, double_width=True, bold=True, density=3)
                self.printer.text(text)
                self.printer.ln(4)
                self.printer.set(align='center', normal_textsize=True)
                self.printer.cut()
                self.printer.close()

                return True
            except Exception as e:
                print(f"Print text error: {str(e)}")
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
        self.clear_label_data_buffer()

    def print_heading(self, order):
        self.printer.ln(1)
        self.printer.set(align='center', double_height=True, double_width=True, bold=True, density=3)
        self.printer.text(format_string(f"Order #: {str(order).title()}", True))
        self.clear_label_data_buffer()

    def print_paid(self):
        self.printer.ln(1)
        self.printer.set(align='center', double_height=True, double_width=True, bold=True, density=3)
        self.printer.text(format_string("PAID", True))
        self.printer.ln(1)
        self.clear_label_data_buffer()

    def print_details(self, item, item_number=None, item_total=None):
        self.printer.ln(2)
        self.printer.set(align='center', normal_textsize=True)
        if item_number and item_total:
            self.printer.text(format_string(f"{item} ({item_number} of {item_total})", False))
        else:
            self.printer.text(format_string(item, False))

    def print_count(self, item_number, item_total):
        self.printer.ln(2)
        self.printer.set(align='center', normal_textsize=True)
        self.printer.text(format_string(f"({item_number} of {item_total})", False))

    def print_barcode(self, upc):
        upc_str = str(upc)

        if not upc_str.isdigit() or len(upc_str) != 12:
            print(f"Error: Invalid UPC format. Received: {upc}")
            self.print_message("Invalid UPC")
            return
        
        #self.printer.ln(2)
        self.printer.barcode(upc_str, 'UPC-A', 32, 2, '', 'A', True, 'B')
        self.clear_label_data_buffer()
    
    def print_gap(self):
        self.printer.ln(3)

    def print_qr(self, fulfillment, item):
        self.printer.set(align='center', normal_textsize=True)
        self.printer.text("Scan for $7 Amazon Gift Card")
        self.printer.ln(2)
        self.printer.qr(content=f"{FEEDBACK_URL}?meta={fulfillment}&item={item}", ec=QR_ECLEVEL_M, size=5, model=2, native=True, center=False, impl=None, image_arguments=None)
        self.clear_label_data_buffer()

    def clear_label_data_buffer(self):
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
