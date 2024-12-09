from odoo import http
from odoo.http import request, Response
from .user_authentication import SocialMediaAuth
from .shared_utilities import Upload_image, get_user_profile_image_path
import os
import json
import random
import logging

_logger = logging.getLogger(__name__)


class SocialMedia(http.Controller):

    def _handle_options(self):
        headers = SocialMediaAuth.get_cors_headers()
        return request.make_response('', headers=headers)

    @http.route('/social_media/create_post', type='http', auth='public', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def create_post(self, **post):
        """
        Description: Creates a new social media post with an optional image.
        Parameters: description (string), image (file)
        """
        
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        user_auth = SocialMediaAuth.user_auth(self)  # Assuming custom auth method
        headers = SocialMediaAuth.get_cors_headers()  # Assuming custom method to get CORS headers

        if user_auth.get('status') == 'error':
            return Response(json.dumps({
                'status': 'error',
                'message': user_auth['message'],
                'info': 'Authentication failed'
            }), content_type='application/json', headers=headers, status=401)

        image_file = request.httprequest.files.get('image')
        description = post.get('description', '')

        if not image_file:
            return Response(json.dumps({
                'status': 'error',
                'message': 'Image file is required',
                'info': 'No image provided'
            }), content_type='application/json', headers=headers, status=400)

        try:
            # Ensure the directory exists
            file_path = Upload_image(image_file)
            # Create the post in the database, storing the image path
            post = request.env['social_media.post'].create({
                'image': file_path,
                'description': description,
                'user_id': user_auth['user_id']
            })

            return Response(json.dumps({
                'status': 'success',
                'post_id': post.id,
                'image_path': file_path
            }), content_type='application/json', headers=headers)

        except Exception as e:
            _logger.error('Error creating social media post: %s', str(e))
            return Response(json.dumps({
                'status': 'error',
                'message': 'Failed to create post',
                'info': str(e)
            }), content_type='application/json', headers=headers, status=500)
        

    @http.route('/social_media/get_posts', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    def get_posts(self):
        """
        Retrieve posts from social media model. It filters out posts from blacklisted users and formats the response.
        Parameters: None
        """
        # Handle OPTIONS request for CORS preflight
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        try:
            user_auth = SocialMediaAuth.user_auth(self)
            if user_auth['status'] == 'error':
                return Response(json.dumps({
                    "status": "error",
                    "message": "Non autorizzato",  # Italian for 'Unauthorized'
                    "info": "The user authentication failed"
                }), content_type='application/json', status=401, headers={'Access-Control-Allow-Origin': '*'})

            posts = request.env['social_media.post'].search([])
            user_data = request.env['res.users'].sudo().search([('id', '=', user_auth['user_id'])])
            user_data = user_data.read(['blocked_users'])
            blocked_users = user_data[0]['blocked_users']

            posts_data = [post for post in posts.read(['id', 'image', 'description', 'timestamp', 'user_id'])
                          if post['user_id'][0] not in blocked_users]

            overall_data = []
            for post in posts_data:
                if post['user_id'][0] in blocked_users:
                    continue

                user_info = request.env['res.users'].sudo().search([('id', '=', post['user_id'][0])])
                
                profile_image = get_user_profile_image_path(user_info.id)

                post.update({
                    'profile_image': profile_image,
                    'user_name': f'{user_info.name} {user_info.x_last_name}',
                    'image': post['image'] if post['image'] else None,
                    'timestamp': post['timestamp'].isoformat() if post['timestamp'] else None,
                    'is_liked': bool(request.env['social_media.like'].search(
                        [('user_id', '=', user_auth['user_id']), ('post_id', '=', post['id'])])),
                    'likes': request.env['social_media.like'].search_count([('post_id', '=', post['id'])]),
                    'comments_count': request.env['social_media.comment'].search_count([('post_id', '=', post['id'])]),
                    'owner': post['user_id'][0] == user_auth['user_id']
                })

                overall_data.append(post)


            overall_data.reverse()

            return Response(json.dumps({"result":{
                "status": "success",
                "message": "Operazione riuscita", 
                "posts": overall_data,
                "info": f"Retrieved {len(overall_data)} posts"
            }}), content_type='application/json', headers={'Access-Control-Allow-Origin': '*'})
        
        except Exception as e:
            return Response(json.dumps({
                "status": "error",
                "message": "Errore del server interno",  # Italian for 'Internal Server Error'
                "info": str(e)
            }), content_type='application/json', status=500, headers={'Access-Control-Allow-Origin': '*'})
        
        
    @http.route('/images/community/<path:image>', type='http', auth='public', csrf=False, cors='*')
    def get_image(self, image):
        """
        Retrieve an image from the community images directory.
        Parameters: image - The path of the image to retrieve.
        """
        image_path = os.path.join('/mnt/extra-addons/images/community', image)
        if os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                image_data = f.read()
            return Response(image_data, content_type='image/png')
        else:
            return Response(json.dumps({
                "status": "error",
                "message": "Immagine non trovata",  # Italian for 'Image not found'
                "info": "The requested image was not found on the server"
            }), content_type='application/json', status=404)


    @http.route('/social_media/delete_post/<int:post_id>', type='http', auth='public', methods=['DELETE', 'OPTIONS'], csrf=False, cors='*')
    def delete_post(self, post_id):
        """
        Delete a post based on its ID if the authenticated user is the owner.
        Parameters: post_id - The ID of the post to delete.
        """
        # Handle OPTIONS request for CORS preflight
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        try:
            user_auth = SocialMediaAuth.user_auth(self)
            if user_auth['status'] == 'error':
                return Response(json.dumps({
                    "status": "error",
                    "message": "Non autorizzato",  # Italian for 'Unauthorized'
                    "info": "User authentication failed"
                }), content_type='application/json', status=401)

            post = request.env['social_media.post'].search([('id', '=', post_id)])
            if not post:
                return Response(json.dumps({
                    "status": "error",
                    "message": "Post non esiste",  # Italian for 'Post does not exist'
                    "info": "The post with the specified ID does not exist"
                }), content_type='application/json', status=404)

            if post.user_id.id != user_auth['user_id']:
                return Response(json.dumps({
                    "status": "error",
                    "message": "Non autorizzato a eliminare questo post",  # Italian for 'Not authorized to delete this post'
                    "info": "You are not authorized to delete this post"
                }), content_type='application/json', status=403)
            
            # remove the image from the directory
            image_path = post.image
            if os.path.exists(image_path):
                os.remove(image_path)

            post.unlink()
            
            
            return Response(json.dumps({
                "status": "success",
                "message": "Post eliminato con successo",  # Italian for 'Post deleted successfully'
                "info": "The post was successfully deleted"
            }), content_type='application/json')

        except Exception as e:
            return Response(json.dumps({
                "status": "error",
                "message": "Errore del server interno",  # Italian for 'Internal Server Error'
                "info": str(e)
            }), content_type='application/json', status=500)

        

    @http.route('/social_media/like', type='json', auth='public', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def like_dislike_post(self):
        """
        Toggle the like status of a post for the authenticated user. If the post is liked, it will be disliked, and vice versa.
        Parameters: None - Post ID is expected in the JSON request.
        """
        # Handle OPTIONS request for CORS preflight
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        try:
            user_auth = SocialMediaAuth.user_auth(self)
            if user_auth['status'] == 'error':
                return {
                    "status": "error",
                    "message": "Non autorizzato",  # Italian for 'Unauthorized'
                    "info": "User authentication failed"
                }, 401

            post_id = request.jsonrequest.get('post_id')
            if not post_id:
                return {
                    "status": "error",
                    "message": "ID del post richiesto",  # Italian for 'post_id is required'
                    "info": "The post ID is required for this operation"
                }, 400

            # if is liked then make it dislike and if not liked then make it like
            default_userId = user_auth['user_id']
            already_like = request.env['social_media.like'].search(
                [('user_id', '=', default_userId), ('post_id', '=', post_id)])

            if already_like:
                already_like.unlink()
                return {
                    "status": "success",
                    "message": "Mi piace rimosso",  # Italian for 'Like removed'
                    "info": "Post disliked successfully"
                }

            like = request.env['social_media.like'].create({
                'user_id': default_userId,
                'post_id': post_id
            })
            return {
                "status": "success",
                "message": "Mi piace aggiunto",  # Italian for 'Like added'
                "info": "Post liked successfully",
                "like_id": like.id
            }

        except Exception as e:
            return {
                "status": "error",
                "message": "Errore del server interno",  # Italian for 'Internal Server Error'
                "info": str(e)
            },500


    @http.route('/social_media/get_likes/<int:post_id>', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    def get_likes(self, post_id):
        """
        Retrieve all likes for a given post along with user information.
        Parameters: post_id - The ID of the post for which likes are being retrieved.
        """
        # Handle OPTIONS request for CORS preflight
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        try:
            user_auth = SocialMediaAuth.user_auth(self)
            if user_auth['status'] == 'error':
                return Response(json.dumps({
                    "status": "error",
                    "message": "Non autorizzato",  # Italian for 'Unauthorized'
                    "info": "User authentication failed"
                }), content_type='application/json', status=401)

            likes = request.env['social_media.like'].search([('post_id', '=', post_id)])
            likes_data = likes.read(['user_id', 'timestamp'])

            # Convert timestamp to ISO 8601 format if present
            for like in likes_data:
                user_info = request.env['res.users'].sudo().search([('id', '=', like['user_id'][0])])
                image_dir = f'images/profilepics/{user_info.id}'
                profile_image = f'{image_dir}/{os.listdir(image_dir)[0]}' if os.path.exists(image_dir) and os.listdir(image_dir) else None

                like.update({
                    'profile_image': profile_image,
                    'user_name': f'{user_info.name} {user_info.x_last_name}',
                    'timestamp': like['timestamp'].isoformat() if like['timestamp'] else None
                })

            result = {
                "status": "success",
                "message": "Mi piace recuperati con successo",  # Italian for 'Likes successfully retrieved'
                "info": f"Retrieved likes for post ID {post_id}",
                "likes": likes_data
            }
            return Response(json.dumps({"result":result}), content_type='application/json')

        except Exception as e:
            return Response(json.dumps({
                "status": "error",
                "message": "Errore del server interno",  # Italian for 'Internal Server Error'
                "info": str(e)
            }), content_type='application/json', status=500)


    @http.route('/social_media/add_comment', type='json', auth='public', methods=['POST', 'OPTIONS'])
    def create_comment(self):
        """
        Create a comment on a post for the authenticated user.
        Parameters: None - Post ID and content are expected in the JSON request.
        """
        # Handle OPTIONS request for CORS preflight
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        try:
            user_auth = SocialMediaAuth.user_auth(self)
            if user_auth['status'] == 'error':
                return {
                    "status": "error",
                    "message": "Non autorizzato",  # Italian for 'Unauthorized'
                    "info": "User authentication failed"
                }, 401

            post_id = request.jsonrequest.get('post_id')
            content = request.jsonrequest.get('content')
            if not post_id or not content:
                return {
                    "status": "error",
                    "message": "ID del post e contenuto sono richiesti",  # Italian for 'Both post_id and content are required'
                    "info": "Both post ID and content must be provided for comment creation"
                }, 400

            comment = request.env['social_media.comment'].create({
                'user_id': user_auth['user_id'],
                'post_id': int(post_id),
                'content': content
            })
            return {
                "status": "success",
                "message": "Commento creato con successo",  # Italian for 'Comment created successfully'
                "info": f"Comment ID {comment.id} added to post ID {post_id}"
            }

        except Exception as e:
            return {
                "status": "error",
                "message": "Errore del server interno",  # Italian for 'Internal Server Error'
                "info": str(e)
            }, 500
        

    # report comment in comment_report by taking comment_id in body
    @http.route('/social_media/report_comment', type='json', auth='public', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def report_comment(self):
        """
        Report a comment as inappropriate by the authenticated user. The method handles both reporting and unreporting of a comment.
        Parameters: None - Comment ID is expected in the JSON request.
        """
        # Handle OPTIONS request for CORS preflight
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        try:
            user_auth = SocialMediaAuth.user_auth(self)
            if user_auth['status'] == 'error':
                return {
                    "status": "error",
                    "message": "Non autorizzato",  # Italian for 'Unauthorized'
                    "info": "User authentication failed, unable to report the comment"
                }, 401

            comment_id = request.jsonrequest.get('comment_id')
            if not comment_id:
                return {
                    "status": "error",
                    "message": "ID del commento richiesto",  # Italian for 'Comment ID required'
                    "info": "Comment ID is required for reporting"
                }, 400

            # Checking if the comment has already been reported by the user
            already_reported = request.env['social_media.comment_report'].search(
                [('user_id', '=', user_auth['user_id']), ('comment_id', '=', comment_id)])

            if already_reported:
                already_reported.unlink()
                return {
                    "status": "success",
                    "message": "Segnalazione commento annullata con successo",  # Italian for 'Comment report successfully undone'
                    "info": "Report for the comment has been successfully removed"
                }

            report = request.env['social_media.comment_report'].create({
                'user_id': user_auth['user_id'],
                'comment_id': comment_id
            })
            return {
                "status": "success",
                "message": "Commento segnalato con successo",  # Italian for 'Comment successfully reported'
                "info": f"Comment report ID {report.id} has been successfully created"
            }

        except Exception as e:
            return {
                "status": "error",
                "message": "Errore del server interno",  # Italian for 'Internal Server Error'
                "info": str(e)
            }, 500

    
    @http.route('/social_media/get_comments/<int:post_id>', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    def get_comments(self, post_id):
        """
        Retrieve all comments for a given post along with user information, like status, and total likes for each comment.
        Parameters: post_id - The ID of the post for which comments are being retrieved.
        """
        # Handle OPTIONS request for CORS preflight
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        try:
            user_auth = SocialMediaAuth.user_auth(self)
            if user_auth['status'] == 'error':
                return Response(json.dumps({
                    "status": "error",
                    "message": "Non autorizzato",  # Italian for 'Unauthorized'
                    "info": "User authentication failed"
                }), content_type='application/json', status=401)

            if not post_id:
                return Response(json.dumps({
                    "status": "error",
                    "message": "ID del post richiesto",  # Italian for 'post_id is required'
                    "info": "The post ID is required for retrieving comments"
                }), content_type='application/json', status=400)

            comments = request.env['social_media.comment'].search([('post_id', '=', post_id)])
            comments_data = comments.read(['user_id', 'content', 'timestamp'])

            for comment in comments_data:
                user_info = request.env['res.users'].sudo().search([('id', '=', comment['user_id'][0])])

                profile_image = get_user_profile_image_path(user_info.id)

                comment.update({
                    'profile_image': profile_image,
                    'user_name': f'{user_info.name} {user_info.x_last_name}',
                    'timestamp': comment['timestamp'].isoformat() if 'timestamp' in comment and comment['timestamp'] else None,
                    'is_liked': bool(request.env['social_media.comment_like'].search(
                        [('user_id', '=', user_auth['user_id']), ('comment_id', '=', comment['id'])])),
                    'likes_count': request.env['social_media.comment_like'].search_count([('comment_id', '=', comment['id'])])
                })
            final_data = {
                "status": "success",
                "message": "Commenti recuperati con successo",  # Italian for 'Comments retrieved successfully'
                "info": f"Retrieved comments for post ID {post_id}",
                "comments": comments_data
            }
            return Response(json.dumps({"result":final_data}), content_type='application/json')

        except Exception as e:
            return Response(json.dumps({
                "status": "error",
                "message": "Errore del server interno",  # Italian for 'Internal Server Error'
                "info": str(e)
            }), content_type='application/json', status=500)


    @http.route('/social_media/delete_comment/<int:comment_id>', type='http', auth='user', methods=['DELETE', 'OPTIONS'], csrf=False, cors='*')
    def delete_comments(self, comment_id):
        """
        Delete a comment based on its ID if the authenticated user is the owner of the comment.
        Parameters: comment_id - The ID of the comment to delete.
        """
        # Handle OPTIONS request for CORS preflight
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        try:
            user_auth = SocialMediaAuth.user_auth(self)
            if user_auth['status'] == 'error':
                return Response(json.dumps({
                    "status": "error",
                    "message": user_auth.get('message', 'Non autorizzato'),  # Defaulting to Italian 'Unauthorized'
                    "info": "User authentication failed"
                }), content_type='application/json', status=401)

            if not comment_id:
                return Response(json.dumps({
                    "status": "error",
                    "message": "comment_id è richiesto",  # Italian for 'comment_id is required'
                    "info": "The comment ID is required for deletion"
                }), content_type='application/json', status=400)

            comment = request.env['social_media.comment'].search([('id', '=', comment_id)])
            if not comment:
                return Response(json.dumps({
                    "status": "error",
                    "message": "Il commento non esiste",  # Italian for 'The comment does not exist'
                    "info": "No comment found with the provided ID"
                }), content_type='application/json', status=404)

            if comment.user_id.id != user_auth['user_id']:
                return Response(json.dumps({
                    "status": "error",
                    "message": "Non sei autorizzato a eliminare questo commento",  # Italian for 'You are not authorized to delete this comment'
                    "info": "Only the owner of the comment can delete it"
                }), content_type='application/json', status=403)

            comment.unlink()
            final_resp = {
                "status": "success",
                "message": "Commento eliminato con successo",  # Italian for 'Comment successfully deleted'
                "info": "The comment has been successfully deleted"
            }
            return Response(json.dumps({"result":final_resp}), content_type='application/json')

        except Exception as e:
            return Response(json.dumps({
                "status": "error",
                "message": "Errore durante l'eliminazione del commento",  # Italian for 'Error during comment deletion'
                "info": str(e)
            }), content_type='application/json', status=500)    

        

    @http.route('/social_media/like_comment', type='json', auth='public', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def like_comment(self):
        """
        Toggle the like status of a comment for the authenticated user. If the comment is liked, it will be disliked, and vice versa.
        Parameters: None - Comment ID is expected in the JSON request.
        """
        # Handle OPTIONS request for CORS preflight
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        try:
            user_auth = SocialMediaAuth.user_auth(self)
            if user_auth['status'] == 'error':
                return Response(json.dumps({
                    "status": "error",
                    "message": "Non autorizzato",  # Italian for 'Unauthorized'
                    "info": "User authentication failed"
                }), content_type='application/json', status=401)

            comment_id = request.jsonrequest.get('comment_id')
            if not comment_id:
                return Response(json.dumps({
                    "status": "error",
                    "message": "ID del commento richiesto",  # Italian for 'comment_id is required'
                    "info": "Comment ID is required for this operation"
                }), content_type='application/json', status=400)

            # if user has liked the comment then make it dislike and if not liked then make it like
            already_like = request.env['social_media.comment_like'].search(
                [('user_id', '=', user_auth['user_id']), ('comment_id', '=', comment_id)])
            if already_like:
                already_like.unlink()
                return {
                    "status": "success",
                    "message": "Mi piace al commento rimosso",  # Italian for 'Like on the comment removed'
                    "info": "Comment disliked successfully"
                }

            like = request.env['social_media.comment_like'].create({
                'user_id': user_auth['user_id'],
                'comment_id': comment_id
            })
            return {
                "status": "success",
                "message": "Mi piace al commento aggiunto",  # Italian for 'Like on the comment added'
                "info": f"Comment liked successfully, like ID {like.id}"
            }

        except Exception as e:
            return  {
                "status": "error",
                "message": "Errore del server interno",  # Italian for 'Internal Server Error'
                "info": str(e)
            }, 500
        



    @http.route('/social_media/get_comment_likes/<int:comment_id>', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    def get_comment_likes(self, comment_id):
        """
        Retrieve all likes for a given comment, including the user who liked and the timestamp of the like.
        Parameters: comment_id - The ID of the comment for which likes are being retrieved.
        """
        # Handle OPTIONS request for CORS preflight
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        try:
            user_auth = SocialMediaAuth.user_auth(self)
            if user_auth['status'] == 'error':
                return Response(json.dumps({
                    "status": "error",
                    "message": "Non autorizzato",  # Italian for 'Unauthorized'
                    "info": "User authentication failed"
                }), content_type='application/json', status=401)

            if not comment_id:
                return Response(json.dumps({
                    "status": "error",
                    "message": "ID del commento richiesto",  # Italian for 'comment_id is required'
                    "info": "Comment ID is required to retrieve likes"
                }), content_type='application/json', status=400)

            likes = request.env['social_media.comment_like'].search([('comment_id', '=', comment_id)])
            likes_data = likes.read(['user_id', 'timestamp'])

            # Convert timestamp to ISO 8601 format if present
            for like in likes_data:
                if 'timestamp' in like and like['timestamp']:
                    like['timestamp'] = like['timestamp'].isoformat()

            final_resp = {
                "status": "success",
                "message": "Mi piace al commento recuperati con successo",  # Italian for 'Likes on the comment successfully retrieved'
                "info": f"Retrieved likes for comment ID {comment_id}",
                "likes": likes_data
            }
            return Response(json.dumps({"result":final_resp}), content_type='application/json')

        except Exception as e:
            return Response(json.dumps({
                "status": "error",
                "message": "Errore del server interno",  # Italian for 'Internal Server Error'
                "info": str(e)
            }), content_type='application/json', status=500)
        

    # Block or unblock a user
    @http.route('/social_media/block_user', type='json', auth='public', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def block_user(self):
        """
        Block or unblock a user. If the user is currently blocked, they will be unblocked, and vice versa.
        Parameters: None - Blocked user ID is expected in the JSON request.
        """
        # Handle OPTIONS request for CORS preflight
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        try:
            user_auth = SocialMediaAuth.user_auth(self)
            if user_auth['status'] == 'error':
                return {
                    "status": "error",
                    "message": user_auth.get('message', 'Non autorizzato'),  # Defaulting to Italian 'Unauthorized'
                    "info": "User authentication failed"
                }

            blocked_user_id = request.jsonrequest.get('blocked_user_id')
            if not blocked_user_id:
                return {
                    "status": "error",
                    "message": "ID dell'utente da bloccare richiesto",  # Italian for 'Blocked user ID required'
                    "info": "The blocked user ID is required for this operation"
                }

            default_user_id = user_auth['user_id']
            if int(blocked_user_id) == default_user_id:
                return {
                    "status": "error",
                    "message": "Non puoi bloccare o sbloccare te stesso",  # Italian for 'You cannot block or unblock yourself'
                    "info": "A user cannot block or unblock themselves"
                }

            # Fetch the user to block
            blocked_user = request.env['res.users'].sudo().search([('id', '=', blocked_user_id)], limit=1)
            if not blocked_user:
                return {
                    "status": "error",
                    "message": "L'utente da bloccare non esiste",  # Italian for 'The user to block does not exist'
                    "info": "No user found with the provided ID"
                }

            # Fetch the current user's record
            current_user = request.env['res.users'].sudo().search([('id', '=', default_user_id)], limit=1)

            # Check if the user is already blocked
            if blocked_user in current_user.blocked_users:
                current_user.write({'blocked_users': [(3, blocked_user.id)]})  # Removes the user from blocked users
                return {
                    "status": "success",
                    "message": "Utente sbloccato con successo",  # Italian for 'User successfully unblocked'
                    "info": "The user has been successfully unblocked"
                }

            current_user.write({'blocked_users': [(4, blocked_user.id)]})  # Adds the user to blocked users
            return {
                "status": "success",
                "message": "Utente bloccato con successo",  # Italian for 'User successfully blocked'
                "info": "The user has been successfully blocked"
            }

        except Exception as e:
            return {
                "status": "error",
                "message": "Errore del server interno",  # Italian for 'Internal Server Error'
                "info": str(e)
            }, 500

        

    @http.route('/social_media/report_post', type='json', auth='public', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def report_post(self):
        """
        Report a post for review. Prevents duplicate reports by the same user on the same post.
        Parameters: None - Post ID is expected in the JSON request.
        """
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        user_auth = SocialMediaAuth.user_auth(self)
        if user_auth['status'] == 'error':
            return {
                "status": "error",
                "message": user_auth.get('message', 'Non autorizzato'),  # Defaulting to Italian 'Unauthorized'
                "info": "User authentication failed"
            }, 401

        post_id = request.jsonrequest.get('post_id')
        if not post_id:
            return {
                "status": "error",
                "message": "ID del post richiesto",  # Italian for 'Post ID required'
                "info": "The post ID is required to report the post"
            }, 400

        default_user_id = user_auth['user_id']
        report = request.env['social_media.report'].search([('post_id', '=', post_id), ('user_id', '=', default_user_id)])
        if report:
            return {
                "status": "error",
                "message": "Post già segnalato",  # Italian for 'Post already reported'
                "info": "You have already reported this post"
            }

        try:
            report = request.env['social_media.report'].create({
                'post_id': post_id,
                'user_id': default_user_id
            })
            return {
                "status": "success",
                "message": "Post segnalato con successo",  # Italian for 'Post successfully reported'
                "info": f"Report ID {report.id} has been successfully created"
            }

        except Exception as e:
            return {
                "status": "error",
                "message": "Errore del server interno",  # Italian for 'Internal Server Error'
                "info": str(e)
            }, 500

    
    @http.route('/social_media/get_reported_posts', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    def get_reported_posts(self):
        """
        Retrieve all reported posts with the details of the reporting users.
        Parameters: None
        """
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options()

        try:
            reported_posts = request.env['social_media.report'].search([])
            reported_posts_data = reported_posts.read(['post_id', 'user_id'])

            return Response(json.dumps({"result":{
                "status": "success",
                "message": "Post segnalati recuperati con successo",  # Italian for 'Reported posts successfully retrieved'
                "info": f"Retrieved {len(reported_posts_data)} reported posts",
                "reported_posts": reported_posts_data
            }}), content_type='application/json')

        except Exception as e:
            return Response(json.dumps({
                "status": "error",
                "message": "Errore del server interno",  # Italian for 'Internal Server Error'
                "info": str(e)
            }), content_type='application/json', status=500)
        
    