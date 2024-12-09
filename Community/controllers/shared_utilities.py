import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
from dotenv import load_dotenv
import random
import base64

load_dotenv()

def generate_password(email):
   characters = ["!", "@", "#", "$", "%", "&", "*"]
   test = email.split('@')[0].capitalize()
   return test + characters[random.randint(0, 6)] + str(random.randint(111, 458962))

def forgot_password(email, password, to_email):
   return True 

def get_user_profile_image_path(user_id):
   image_dir = f'/mnt/extra-addons/images/profilepics/{user_id}'
   if os.path.exists(image_dir) and os.listdir(image_dir):
       return f'{image_dir}/{os.listdir(image_dir)[0]}'.replace('/mnt/extra-addons/', '')
   return 'None'

def save_user_image(user_id, image_data):
   if not image_data:
       return 'None'

   save_directory = f'/mnt/extra-addons/images/profilepics/{user_id}'
   os.makedirs(save_directory, exist_ok=True)

   for file in os.listdir(save_directory):
       os.remove(os.path.join(save_directory, file))

   image_filename = f'profile_{random.randint(1, 5000)}_{user_id}.png'
   image_path = os.path.join(save_directory, image_filename)

   with open(image_path, 'wb') as file:
       file.write(base64.b64decode(image_data))

   return image_path.replace('/mnt/extra-addons/', '')