#!/usr/bin/env python
from samplebase import SampleBase


class MaxBrightnessYellow(SampleBase):
    def __init__(self, *args, **kwargs):
        super(MaxBrightnessYellow, self).__init__(*args, **kwargs)

    def run(self):
        # Set the matrix to maximum brightness
        self.matrix.brightness = self.matrix.brightness

        # Fill the matrix with light yellow color at maximum brightness
        self.matrix.Fill(255, 255, 102)  # RGB values for light yellow

        # Keep the program running
        while True:
            self.usleep(1000000)  # Sleep for 1 second

# Main function
if __name__ == "__main__":
    max_brightness_yellow = MaxBrightnessYellow()
    if (not max_brightness_yellow.process()):
        max_brightness_yellow.print_help()
