import time
from escpos.printer import Usb

class PrinterManager:
    def __init__(self):
        self.make = 0x1234
        self.model = 0x5678
        self.profile = "TM-T88IV"
        self.status = "Unknown"
        self.last_log = ""
        self.poll_interval = 5
        self.printer = None

    def get_status(self):
        return self.status

    def print(self, order, sku):
        self.check_status()
        if self.status != "ready":
            return False
        try:
            print("Printing")
            # Print order number
            self.printer.set(align='center')
            self.printer.text("Order # ")
            self.printer.ln()
            self.printer.set(align='center', double_height=True, double_width=True, bold=True)
            self.printer.text(str(order))
            self.printer.set()  # Reset text size to default
            self.printer.ln(2)
            self.printer.text("3 Tender Combo")
            
            self.printer.ln(2)
    
            fake_ean13_code = f'900000000000{sku}'
            self.printer.barcode(fake_ean13_code, 'EAN13', 64, 2, '', '')
                
            self.printer.cut()
            return True
        except Exception as e:
            self.last_log = f"Print error: {str(e)}"
            print(self.last_log)
            return False
        finally:
            self.printer.close()

    def check_status(self):
        try:
            print("Checking status")
            prev_status = self.status

            # TODO: ADD TIMEOUT
            self.printer = Usb(self.make, self.model, 0, self.profile)
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
        except Exception as e:
            self.last_log = f"Status check error: {str(e)}"
            print(self.last_log)

    def start_status_checking(self):
        while True:
            self.check_status()
            time.sleep(self.poll_interval)
