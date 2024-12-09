import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
from dotenv import load_dotenv
import random
import base64

load_dotenv()


def generate_password(email):
    """
    Generate a random password using a part of the user's email and random special characters and numbers.
    Parameters:
        email (str): The user's email address.
    Returns:
        str: A randomly generated password.
    """
    characters = ["!", "@", "#", "$", "%", "&", "*"]
    test = email.split('@')[0].capitalize()
    password = test + characters[random.randint(0, 6)] + str(random.randint(111, 458962))
    return password



def forgot_password(email, password, to_email):
    """
    Simulate sending an email for password recovery. This is a placeholder for actual email sending logic.
    Parameters:
        email (str): Email address to send the password reset information to.
        password (str): The new password or reset token.
        to_email (str): The recipient email address.
    Returns:
        bool: True if the email was "sent" successfully, False otherwise.
    """
    return True



def get_user_profile_image_path(user_id):
    """
    Retrieve the path to the user's profile image if it exists.
    Parameters:
        user_id (int): The unique identifier for the user.
    Returns:
        str: The path to the user's profile image or 'None' if no image exists.
    """
    image_dir = f'images/profilepics/{user_id}'
    if os.path.exists(image_dir) and os.listdir(image_dir):
        return f'{image_dir}/{os.listdir(image_dir)[0]}'
    return 'None'



def Upload_image(image_file):
    """
    Save an uploaded image to a designated directory on the server and return its path.
    Parameters:
        image_file (File): The image file to be saved.
    Returns:
        str: The path to the saved image.
    """
    save_directory = '/mnt/extra-addons/images/community'
    os.makedirs(save_directory, exist_ok=True)
    file_path = os.path.join(save_directory, f'post_image_{random.randint(100000, 999999)}.png')
    
    with open(file_path, 'wb') as file:
        file.write(image_file.read())
    return file_path.replace('/mnt/extra-addons/', '')




def save_user_image(user_id, image_data):
    """
    Save the user's profile image and return the path.
    Parameters:
        user_id (int): The unique identifier for the user.
        image_data (str): Base64 encoded string of the image.
    Returns:
        str: The path to the saved image or 'None' if no image was provided.
    """
    if not image_data:
        return 'None'  # Return 'None' if there is no image data

    save_directory = f'images/profilepics/{user_id}'
    os.makedirs(save_directory, exist_ok=True)  # Ensure directory exists

    # if there already exists a profile image, delete it
    for file in os.listdir(save_directory):
        os.remove(os.path.join(save_directory, file))

    image_filename = f'profile_{random.randint(1, 5000)}_{user_id}.png'
    image_path = os.path.join(save_directory, image_filename)

    with open(image_path, 'wb') as file:
        file.write(base64.b64decode(image_data))

    return f'/{image_path}'