#!/usr/bin/env python
from samplebase import SampleBase


class MaxBrightnessWhite(SampleBase):
    def __init__(self, *args, **kwargs):
        super(MaxBrightnessWhite, self).__init__(*args, **kwargs)

    def run(self):
        # Set the matrix to maximum brightness
        self.matrix.brightness = self.matrix.brightness

        # Get the width and height of the matrix
        width = self.matrix.width
        height = self.matrix.height

        # Calculate the height of each section (25% of the total height)
        section_height = height // 4

        # Fill the matrix with the desired pattern
        for y in range(height):
            if y < section_height or (2 * section_height <= y < 3 * section_height):
                # Fill these sections with white color
                for x in range(width):
                    self.matrix.SetPixel(x, y, 255, 255, 255)
            # The other sections remain off (black)

        # Keep the program running
        while True:
            self.usleep(1000000)  # Sleep for 1 second

# Main function
if __name__ == "__main__":
    max_brightness_white = MaxBrightnessWhite()
    if (not max_brightness_white.process()):
        max_brightness_white.print_help()
