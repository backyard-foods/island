import time
from escpos.printer import Usb
from escpos.exceptions import DeviceNotFoundError
import threading
import json
from utils import restart_container, format_string

LOG_PREFIX = "[receipt-printer]"
# ~270x50 PNG, black on transparent
LOGO_PATH = "receipt-logo.png"

MAKE = 0x04b8 # Epson
MODELS = [0x0e2e, 0x0202] # Supported models: EU-m30, TM-T88IV
PROFILE = "TM-T88IV"

#EU-m30 Settings
LOGO_FRAGMENT_HEIGHT = 2
LOGO_SLEEP_BETWEEN_FRAGMENTS_MS = 50
SLEEP_BETWEEN_SEGMENTS_MS = 50

POLL_INTERVAL = 30
PRINT_COOLDOWN = 4
POLL_COOLDOWN = 1

class ReceiptPrinterManager:
    def __init__(self, byf_client):
        self.poll_interval = POLL_INTERVAL
        self.cooldown = PRINT_COOLDOWN
        self.last_request_time = 0
        self.lock = threading.Lock()
        self.status = "offline"
        self.last_log = ""
        self.byf_client = byf_client
        self.printer = None

        self.initialize_printer()

    def initialize_printer(self):
        for model in MODELS:
            try:
                self.printer = Usb(idVendor=MAKE, idProduct=model, usb_args={}, timeout=self.poll_interval, profile=PROFILE)
                self.printer.open()
                self.printer.close()
                print(f"{LOG_PREFIX} Printer initialized successfully: Vendor ID: {MAKE}, Product ID: {model}")
                self.status = "ready"
                return True
            except DeviceNotFoundError:
                continue
            except Exception as e:
                print(f"{LOG_PREFIX} Error initializing printer with model {model}: {str(e)}")
        
        self.status = "offline"
        self.last_log = "USB printer not found or initialization failed for all models"
        print(f"{LOG_PREFIX} {self.last_log}")
        return False

    def get_status(self):
        return self.status

    def throttle(self, printing=True):
        current_time = time.time()
        elapsed_time = current_time - self.last_request_time
        if elapsed_time < self.cooldown:
            time.sleep(self.cooldown - elapsed_time)
            print(f"{LOG_PREFIX} Throttled for {self.cooldown - elapsed_time} seconds")
        self.last_request_time = time.time()
        if printing:
            self.cooldown = PRINT_COOLDOWN
        else:
            self.cooldown = POLL_COOLDOWN

    def print_receipt(self, order, upcs, details, message, wait):
        with self.lock:
            self.throttle()

            if self.status == "offline":
                return False
            if self.status != "ready":
                self.printer.close()
                return False
            try:
                self.start_print_job()
                self.print_logo()

                if(order):
                    self.print_heading(order)

                if(details):
                    self.print_details(details)
                
                if(wait):
                    self.print_message(f"Pay at register. Your order will be ready in {wait} minutes.")
                else:
                    self.print_message("Pay at register")
                
                if(upcs):
                    try:
                        upcs = json.loads(upcs)
                    except json.JSONDecodeError:
                        print(f"{LOG_PREFIX} Error: Invalid UPC format. Received: {upcs}")
                        upcs = []
                    for upc in upcs:
                        self.print_barcode(upc)
                
                if(message):
                    self.print_message(message)
                
                self.end_print_job()
                
                try:
                    self.byf_client.notify_print_success(order)
                except Exception as e:
                    print(f"{LOG_PREFIX} Failed to notify backend of print success: {e}")
                
                return True
            
            except Exception as e:
                self.last_log = f"Print error: {str(e)}"
                print(f"{LOG_PREFIX} {self.last_log}")
                self.end_print_job()
                return False
    
    def start_print_job(self):
        self.printer.open()
        self.printer.set_sleep_in_fragment(LOGO_SLEEP_BETWEEN_FRAGMENTS_MS)
        self.printer.set(align='center', flip=False)
        print(f"{LOG_PREFIX} Printing")

    def end_print_job(self):
        self.printer.ln(1)
        self.printer.cut()
        self.printer.close()

    def print_logo(self):
        print(f"{LOG_PREFIX} Printing logo")
        self.printer.image(LOGO_PATH,
                           high_density_vertical=True, 
                           high_density_horizontal=True, 
                           impl='bitImageRaster', 
                           fragment_height=LOGO_FRAGMENT_HEIGHT, 
                           center=False)
        self.clear_receipt_data_buffer()


    def print_heading(self, order):
        print(f"{LOG_PREFIX} Printing heading")
        self.printer.ln(1)
        self.printer.set(align='center', double_height=True, double_width=True, bold=True, density=3)
        self.printer.text(format_string(f"Order #: {str(order).title()}", True))
        self.clear_receipt_data_buffer()

    def print_details(self, details):
        print(f"{LOG_PREFIX} Printing details")
        self.printer.ln(2)
        self.printer.set(align='center', normal_textsize=True)
        self.printer.text(format_string(details, False))
        self.clear_receipt_data_buffer()

    def print_barcode(self, upc):
        print(f"{LOG_PREFIX} Printing barcode")
        upc_str = str(upc)

        if not upc_str.isdigit() or len(upc_str) != 12:
            print(f"{LOG_PREFIX} Error: Invalid UPC format. Received: {upc}")
            self.print_message("Invalid UPC")
            return
        
        self.printer.ln(2)
        self.printer.barcode(upc_str, 'UPC-A', 64, 2, '', 'A', True, 'B')
        self.clear_receipt_data_buffer()
    
    def print_message(self, message):
        print(f"{LOG_PREFIX} Printing message")
        self.printer.ln(2)
        self.printer.set(align='center', normal_textsize=True)
        self.printer.text(format_string(message, False))
        self.clear_receipt_data_buffer()

    def clear_receipt_data_buffer(self):
        print(f"{LOG_PREFIX} Clearing receipt data buffer")
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
                self.last_log = f"Reload paper error: {str(e)}"
                print(f"{LOG_PREFIX} {self.last_log}")
                return False
            return True

    def check_status(self):
        with self.lock:
            self.throttle(printing=False)
            try:
                print(f"{LOG_PREFIX} Checking status, last status: {self.status}")
                prev_status = self.status

                if self.printer is None or self.status == "offline":
                    print(f"{LOG_PREFIX} Attempting to reinitialize printer")
                    if not self.initialize_printer():
                        return

                self.printer.open()

                online_status = self.printer.is_online()
                paper_status = self.printer.paper_status()

                print(f"{LOG_PREFIX} Online status: {online_status}, Paper status: {paper_status}")

                if paper_status == 2 and online_status == True:
                    self.status = "ready"
                elif paper_status == 1:
                    self.status = "low_paper" 
                elif paper_status == 0:
                    self.status = "out_of_paper"
                else:
                    self.status = "error"
                
                if prev_status != self.status:
                    self.last_log = f"Printer status changed to: {self.status}"
                    print(f"{LOG_PREFIX} {self.last_log}")
            except DeviceNotFoundError as e:
                self.status = "offline"
                self.last_log = f"Printer not found: {str(e)}"
                print(f"{LOG_PREFIX} {self.last_log}")
            except Exception as e:
                self.last_log = f"Status check error: {str(e)}"
                print(f"{LOG_PREFIX} {self.last_log}")
            finally:
                if self.printer:
                    self.printer.close()
        if self.status == "offline":
            restart_container()

    def start_status_checking(self):
        while True:
            self.check_status()
            time.sleep(self.poll_interval)
