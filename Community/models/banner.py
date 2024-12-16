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

       os.makedirs(directory_path, exist_ok=True)

       # Remove existing files
       for file in os.listdir(directory_path):
           if file.endswith((".jpg", ".png")):
               os.remove(os.path.join(directory_path, file))

       # Write new images
       for i, image in enumerate(images):
           if image:
               path = os.path.join(directory_path, f'slider_{random.randint(1, 56000)}.png')
               with open(path, 'wb') as f:
                   f.write(base64.b64decode(image))