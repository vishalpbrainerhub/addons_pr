from odoo import models, fields, api
import base64
import os
import random

import logging

_logger = logging.getLogger(__name__)

class Banner(models.Model):
    _name = 'social_media.banner'
    _description = 'Banner'

    image_1 = fields.Binary("Image_1")
    image_2 = fields.Binary("Image_2")
    image_3 = fields.Binary("Image_3")

   

    def image_1_url(self):
        directory_path = 'images/banners'
        images = [self.image_1, self.image_2, self.image_3]

        # Ensure the directory exists
        if not os.path.exists(directory_path):
            os.makedirs(directory_path)

        for root, dirs, files in os.walk(directory_path):
            for index, file in enumerate(files):
                if file.endswith(".jpg") or file.endswith(".png"):
                    # Remove existing file
                    os.remove(os.path.join(root, file))

                    # Calculate a random new file name to avoid conflicts
                    new_image_path = os.path.join(root, f'slider_{random.randint(1, 56000)}.png')
                    
                    # Check if the index is within the range of available images
                    if index < len(images) and images[index]:
                        # Write the new image
                        with open(new_image_path, 'wb') as f:
                            f.write(base64.b64decode(images[index]))

        