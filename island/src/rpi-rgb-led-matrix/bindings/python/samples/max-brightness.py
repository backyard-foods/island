#!/usr/bin/env python
from samplebase import SampleBase


class MaxBrightnessWhite(SampleBase):
    def __init__(self, *args, **kwargs):
        super(MaxBrightnessWhite, self).__init__(*args, **kwargs)

    def run(self):
        # Set the matrix to maximum brightness
        self.matrix.brightness = self.matrix.brightness

        # Fill the matrix with white color at maximum brightness
        self.matrix.Fill(255, 255, 255)

        # Keep the program running
        while True:
            self.usleep(1000000)  # Sleep for 1 second

# Main function
if __name__ == "__main__":
    max_brightness_white = MaxBrightnessWhite()
    if (not max_brightness_white.process()):
        max_brightness_white.print_help()
