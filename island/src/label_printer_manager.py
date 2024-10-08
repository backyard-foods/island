import time
from escpos.printer import Usb
from escpos.exceptions import DeviceNotFoundError
#from PIL import Image
import threading
from utils import restart_container, format_string

LOG_PREFIX = "[label-printer]"

# TM-L00 printer
MAKE = 0x04b8
MODEL = 0x0e31
PROFILE = "TM-L90"  # Wrong profile for the TM-L00, but no issues so far
POLL_INTERVAL = 30
COOLDOWN = 5

class LabelPrinterManager:
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

    def print_label(self, order, item, item_number, item_total, fulfillment=None):
        print(f"{LOG_PREFIX} Printing label for order: {order}, item: {item}, item_number: {item_number}, item_total: {item_total}, fulfillment: {fulfillment}")
        with self.lock:
            self.throttle()

            if self.status != "ready":
                self.printer.close()
                return False
            try:
                self.start_print_job()

                if(order):
                    self.print_heading(order)

                if(item):
                    self.print_details(item)
                
                try:
                    if(int(item_total) > 1 and int(item_number) > 0):
                        self.print_count(item_number, item_total)
                except ValueError:
                    print(f"{LOG_PREFIX} Invalid item_total value: {item_total}")
                
                self.end_print_job()
                
                if fulfillment:
                    try:
                        self.byf_client.notify_label_success(fulfillment)
                    except Exception as e:
                        print(f"{LOG_PREFIX} Failed to notify backend of print success: {e}")
                
                return True
            
            except Exception as e:
                self.last_log = f"Print error: {str(e)}"
                print(f"{LOG_PREFIX} {self.last_log}")
                self.end_print_job()
                return False
            
    def print_text(self, text):
        print(f"{LOG_PREFIX} Printing text: {text}")
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
            except Exception as e:
                self.last_log = f"Print text error: {str(e)}"
                print(f"{LOG_PREFIX} {self.last_log}")
    
    def start_print_job(self):
        self.printer.open()
        print(f"{LOG_PREFIX} Printing")

    def end_print_job(self):
        self.printer.ln(2)
        self.printer.cut()
        self.printer.close()

    def print_heading(self, order):
        self.printer.ln(2)
        self.printer.set(align='center', double_height=True, double_width=True, bold=True, density=3)
        self.printer.text(format_string(f"Order #: {str(order).title()}", True))
        self.clear_label_data_buffer()

    def print_details(self, details):
        self.printer.ln(2)
        self.printer.set(align='center', normal_textsize=True)
        self.printer.text(format_string(details, False))

    def print_count(self, item_number, item_total):
        self.printer.ln(2)
        self.printer.set(align='center', normal_textsize=True)
        self.printer.text(format_string(f"({item_number} of {item_total})", False))

    def clear_label_data_buffer(self):
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
