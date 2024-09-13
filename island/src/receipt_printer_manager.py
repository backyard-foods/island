import time
from escpos.printer import Usb
from escpos.exceptions import DeviceNotFoundError
#from PIL import Image
import threading
import json
from byf_api_client import BYFAPIClient
from utils import restart_container, format_string

LOG_PREFIX = "[receipt-printer]"

# TM-T88IV printer
MAKE = 0x04b8
MODEL = 0x0202
PROFILE = "TM-T88IV"
POLL_INTERVAL = 30
COOLDOWN = 5

class ReceiptPrinterManager:
    def __init__(self, byf_client):
        self.poll_interval = POLL_INTERVAL
        self.printer = Usb(idVendor=MAKE, idProduct=MODEL, usb_args={}, timeout=self.poll_interval, profile=PROFILE)
        self.cooldown = COOLDOWN
        self.last_request_time = 0
        self.lock = threading.Lock()
        self.status = "Unknown"
        self.last_log = ""
        self.byf_client = byf_client

    def get_status(self):
        return self.status

    def throttle(self):
        current_time = time.time()
        elapsed_time = current_time - self.last_request_time
        if elapsed_time < self.cooldown:
            time.sleep(self.cooldown - elapsed_time)
            print(f"{LOG_PREFIX} Throttled for {self.cooldown - elapsed_time} seconds")
        self.last_request_time = time.time()

    def print_receipt(self, order, skus, details, message):
        
        with self.lock:
            self.throttle()

            if self.status != "ready":
                self.printer.close()
                return False
            try:
                self.start_print_job()
                #self.print_logo()

                if(order):
                    self.print_heading(order)

                if(details):
                    self.print_details(details)
                
                if(skus):
                    try:
                        skus = json.loads(skus)
                    except json.JSONDecodeError:
                        print(f"{LOG_PREFIX} Error: Invalid SKU format. Received: {skus}")
                        skus = []
                    for sku in skus:
                        self.print_barcode(sku)
                
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
        print(f"{LOG_PREFIX} Printing")

    def end_print_job(self):
        self.printer.ln(2)
        self.printer.cut()
        self.printer.close()

    def print_logo(self):
        # Print logo
        image = Image.open('logo_ready.bmp')
        image = Image.open('logo.png')
        image = image.convert('1')  # Convert to 1-bit black and white
        image.save('logo_ready.bmp')  # Save it as BMP if needed
        self.printer.image(image)
        self.clear_receipt_data_buffer()

    def print_heading(self, order):
        self.printer.ln(2)
        self.printer.set(align='center', double_height=True, double_width=True, bold=True, density=3)
        self.printer.text(format_string(f"Order #: {str(order).title()}", True))
        self.clear_receipt_data_buffer()

    def print_details(self, details):
        self.printer.ln(2)
        self.printer.set(align='center', normal_textsize=True)
        self.printer.text(format_string(details, False))

    def print_barcode(self, sku):
        self.printer.ln(2)
        sku_str = str(sku).zfill(12)[-12:]
        fake_ean13_code = f'9{sku_str}'
        self.printer.barcode(fake_ean13_code, 'EAN13', 64, 2, '', '')
        self.clear_receipt_data_buffer()
    
    def print_message(self, message):
        self.printer.ln(2)
        self.printer.set(align='center', normal_textsize=True)
        self.printer.text(format_string(message, False))

    def clear_receipt_data_buffer(self):
        time.sleep(0.3)

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
            self.throttle()
            try:
                print(f"{LOG_PREFIX} Checking status, last status: {self.status}")
                prev_status = self.status
                
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
                self.printer.close()
        if self.status == "offline":
            restart_container()

    def start_status_checking(self):
        while True:
            self.check_status()
            time.sleep(self.poll_interval)
