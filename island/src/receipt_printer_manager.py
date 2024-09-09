import time
from escpos.printer import Usb
from escpos.exceptions import DeviceNotFoundError
#from PIL import Image
import threading
import os
import requests
import json
from byf_api_client import BYFAPIClient

class ReceiptPrinterManager:
    def __init__(self):
        self.make = 0x04b8
        self.model = 0x0202
        self.profile = "TM-T88IV"
        self.poll_interval = 30
        self.printer = Usb(idVendor=self.make, idProduct=self.model, usb_args={}, timeout=self.poll_interval, profile=self.profile)
        self.cooldown = 5
        self.last_request_time = 0
        self.lock = threading.Lock()
        self.status = "Unknown"
        self.last_log = ""
        self.byf_client = BYFAPIClient()

    def get_status(self):
        return self.status

    def throttle(self):
        current_time = time.time()
        elapsed_time = current_time - self.last_request_time
        if elapsed_time < self.cooldown:
            time.sleep(self.cooldown - elapsed_time)
            print(f"Throttled for {self.cooldown - elapsed_time} seconds")
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
                        print(f"Error: Invalid SKU format. Received: {skus}")
                        skus = []
                    for sku in skus:
                        self.print_barcode(sku)
                
                if(message):
                    self.print_message(message)
                
                self.end_print_job()
                
                try:
                    self.byf_client.notify_print_success(order)
                except Exception as e:
                    print(f"Failed to notify backend of print success: {e}")
                
                return True
            
            except Exception as e:
                self.last_log = f"Print error: {str(e)}"
                print(self.last_log)
                self.end_print_job()
                return False
    
    def start_print_job(self):
        self.printer.open()
        print("Printing")

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
        self.clear_printer_data_buffer()

    def print_heading(self, order):
        self.printer.ln(2)
        self.printer.set(align='center', double_height=True, double_width=True, bold=True, density=3)
        self.printer.text(self.format_string(f"Order #: {str(order).title()}", True))
        self.clear_printer_data_buffer()

    def print_details(self, details):
        self.printer.ln(2)
        self.printer.set(align='center', normal_textsize=True)
        self.printer.text(self.format_string(details, False))

    def print_barcode(self, sku):
        self.printer.ln(2)
        sku_str = str(sku).zfill(12)[-12:]
        fake_ean13_code = f'9{sku_str}'
        self.printer.barcode(fake_ean13_code, 'EAN13', 64, 2, '', '')
        self.clear_printer_data_buffer()
    
    def print_message(self, message):
        self.printer.ln(2)
        self.printer.set(align='center', normal_textsize=True)
        self.printer.text(self.format_string(message, False))

    def clear_printer_data_buffer(self):
        time.sleep(0.3)

    def format_string(self, string, double_size):
        char_limit = 21 if double_size else 38
        lines = []
        
        # Split the input string by newlines first
        for input_line in string.split('\n'):
            words = input_line.split()
            current_line = ""
            
            for word in words:
                if len(current_line) + len(word) + 1 <= char_limit:
                    current_line += " " + word if current_line else word
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            
            if current_line:
                lines.append(current_line)
        
        return '\n'.join(lines)
    
    def reload_paper(self):
        with self.lock:
            self.throttle()
            try:
                self.printer.open()
                self.printer.ln(20)
                self.printer.text("RELOADING PAPER")
                self.printer.ln(20)
                self.printer.cut()
                self.printer.close()
            except Exception as e:
                self.last_log = f"Reload paper error: {str(e)}"
                print(self.last_log)
                return False
            return True

    def check_status(self):
        with self.lock:
            self.throttle()
            try:
                print(f"Checking status, last status: {self.status}")
                prev_status = self.status
                
                self.printer.open()

                online_status = self.printer.is_online()
                paper_status = self.printer.paper_status()

                print(f"Online status: {online_status}, Paper status: {paper_status}")

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
                    print(self.last_log)
            except DeviceNotFoundError as e:
                self.status = "offline"
                self.last_log = f"Printer not found: {str(e)}"
                print(self.last_log)
            except Exception as e:
                self.last_log = f"Status check error: {str(e)}"
                print(self.last_log)
            finally:
                self.printer.close()
        if self.status == "offline":
            self.restart_container()

    def restart_container(self):
        app_id = os.environ['BALENA_APP_ID']
        supervisor_address = os.environ['BALENA_SUPERVISOR_ADDRESS']
        api_key = os.environ['BALENA_SUPERVISOR_API_KEY']

        if not all([app_id, supervisor_address, api_key]):
            print("Error: Missing required environment variables")
            return

        url = f"{supervisor_address}/v1/restart?apikey={api_key}"
        payload = {"appId": app_id}
        
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            print("Container restart request sent successfully")
        except requests.exceptions.RequestException as e:
            print(f"Failed to restart container: {e}")

    def start_status_checking(self):
        while True:
            self.check_status()
            time.sleep(self.poll_interval)
