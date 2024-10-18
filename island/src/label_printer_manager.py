import time
from escpos.printer import Usb
from escpos.constants import QR_ECLEVEL_M
from escpos.exceptions import DeviceNotFoundError
import threading
from utils import restart_container, format_string

LOG_PREFIX = "[label-printer]"
FEEDBACK_URL = "https://backyardfoods.com/feedback"
# ~270x50 PNG, black on transparent
LOGO_PATH = "receipt-logo.png"

# TM-L00 printer
MAKE = 0x04b8
MODEL = 0x0e31
PROFILE = "TM-L90"  # Wrong profile for the TM-L00, but no issues so far
POLL_INTERVAL = 30
PRINT_COOLDOWN = 4
POLL_COOLDOWN = 1

class LabelPrinterManager:
    def __init__(self, byf_client):
        self.poll_interval = POLL_INTERVAL
        self.printer = Usb(idVendor=MAKE, idProduct=MODEL, usb_args={}, timeout=self.poll_interval, profile=PROFILE)
        self.cooldown = PRINT_COOLDOWN
        self.last_request_time = 0
        self.lock = threading.Lock()
        self.status = "Unknown"
        self.last_log = ""
        self.byf_client = byf_client

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

    def print_label(self, order, item, upc, item_number, item_total, fulfillment=None):
        print(f"{LOG_PREFIX} Printing label for order: {order}, item: {item}, upc: {upc}, item_number: {item_number}, item_total: {item_total}, fulfillment: {fulfillment}")
        with self.lock:
            self.throttle()

            if self.status != "ready":
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
                        print(f"{LOG_PREFIX} Invalid item_total value: {item_total}")
                
                if fulfillment and item:
                    self.print_qr(fulfillment, item)
                
                if(upc):
                    self.print_barcode(upc)

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
        self.printer.set(align='center')
        print(f"{LOG_PREFIX} Printing")

    def end_print_job(self):
        self.printer.cut()
        self.printer.close()

    def print_logo(self):
        self.printer.image(LOGO_PATH,
                           high_density_vertical=True, 
                           high_density_horizontal=True, 
                           impl='bitImageRaster', 
                           fragment_height=20, 
                           center=False)
        self.clear_label_data_buffer()

    def print_heading(self, order):
        self.printer.ln(1)
        self.printer.set(align='center', double_height=True, double_width=True, bold=True, density=3)
        self.printer.text(format_string(f"Order #: {str(order).title()}", True))
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
            print(f"{LOG_PREFIX} Error: Invalid UPC format. Received: {upc}")
            self.print_message("Invalid UPC")
            return
        
        #self.printer.ln(2)
        self.printer.barcode(upc_str, 'UPC-A', 32, 2, '', 'A', True, 'B')
        self.clear_label_data_buffer()

    def print_qr(self, fulfillment, item):
        self.printer.ln(3)
        self.printer.set(align='center', normal_textsize=True)
        self.printer.text("How was your order? Scan to let us know:")
        self.printer.ln(2)
        self.printer.qr(content=f"{FEEDBACK_URL}?meta={fulfillment}&item={item}", ec=QR_ECLEVEL_M, size=5, model=2, native=True, center=False, impl=None, image_arguments=None)
        self.clear_label_data_buffer()

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
            self.throttle(printing=False)
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
