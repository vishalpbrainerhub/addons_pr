import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
from dotenv import load_dotenv
import random
import base64

load_dotenv()

def get_base_image_path():
    """Return the base path for all image operations"""
    return '/mnt/data/images'

def generate_password(email):
    characters = ["!", "@", "#", "$", "%", "&", "*"]
    test = email.split('@')[0].capitalize()
    return test + characters[random.randint(0, 6)] + str(random.randint(111, 458962))

def forgot_password(email, password, to_email):
    return True 

def get_user_profile_image_path(user_id):
    base_path = get_base_image_path()
    image_dir = os.path.join(base_path, 'profilepics', str(user_id))
    if os.path.exists(image_dir) and os.listdir(image_dir):
        return os.path.join(image_dir, os.listdir(image_dir)[0])
    return 'None'

def save_user_image(user_id, image_data):
    if not image_data:
        return 'None'

    base_path = get_base_image_path()
    save_directory = os.path.join(base_path, 'profilepics', str(user_id))
    os.makedirs(save_directory, exist_ok=True)

    # Clean up existing files
    for file in os.listdir(save_directory):
        os.remove(os.path.join(save_directory, file))

    image_filename = f'profile_{random.randint(1, 5000)}_{user_id}.png'
    image_path = os.path.join(save_directory, image_filename)

    with open(image_path, 'wb') as file:
        file.write(base64.b64decode(image_data))

    return image_path

def Upload_image(image_file):
    """
    Save an uploaded image to a designated directory on the server and return its path.
    Parameters:
        image_file (File): The image file to be saved.
    Returns:
        str: The path to the saved image.
    """
    base_path = get_base_image_path()
    save_directory = os.path.join(base_path, 'community')
    os.makedirs(save_directory, exist_ok=True)

    file_path = os.path.join(save_directory, f'post_image_{random.randint(100000, 999999)}.png')

    with open(file_path, 'wb') as file:
        file.write(image_file.read())

    return file_path