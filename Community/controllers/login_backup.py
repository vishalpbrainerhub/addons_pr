
    # @http.route('/user/login', type='json', auth='public', methods=['POST', 'OPTIONS'], csrf=False)
    # def login(self):
    #     try:
    #         email = request.jsonrequest.get('email')
    #         password = request.jsonrequest.get('password')

    #         if not email or not password:
    #             return {"status": "error", "message": "Email e password sono richieste"}

    #         customer = request.env['res.partner'].sudo().search([
    #             ('email', '=', email),
    #             ('customer_rank', '>', 0),
    #         ], limit=1)

    #         if not customer:
    #             return {"status": "error", "message": "Credenziali non valide"}

    #         pwd_record = request.env['customer.password'].sudo().search([
    #             ('partner_id', '=', customer.id)
    #         ], limit=1)

    #         if not pwd_record or not pwd_record.verify_password(password):
    #             return {"status": "error", "message": "Credenziali non valide"}

    #         payload = {
    #             'user_id': customer.id,
    #             'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=2)
    #         }
    #         token = jwt.encode(payload, 'testing', algorithm='HS256')

    #         return {
    #             "status": "success",
    #             "message": "Accesso eseguito con successo",
    #             "user": {
    #                 'name': customer.name,
    #                 'email': customer.email,
    #                 'phone': customer.phone,
    #                 'company_id': customer.company_id.id if customer.company_id else False,
    #                 'lang': customer.lang or 'en_US'
    #             },
    #             "token": token if isinstance(token, str) else token.decode('utf-8')
    #         }

    #     except Exception as e:
    #         _logger.error('Login error: %s', str(e))
    #         return {"status": "error", "message": "Errore del server"}
    

    # @http.route('/user/register', type='json', auth='public', methods=['POST', 'OPTIONS'], csrf=False)
    # def register(self):
    #     try:
    #         data = request.jsonrequest
    #         email = data.get('email')
    #         password = data.get('password')
    #         name = data.get('name')

    #         if not email or not password or not name:
    #             return {"status": "error", "message": "Nome, email e password sono richiesti"}

    #         if request.env['res.partner'].sudo().search([('email', '=', email)]):
    #             return {"status": "error", "message": "Email già registrata"}

    #         customer = request.env['res.partner'].sudo().create({
    #             'name': name,
    #             'email': email,
    #             'customer_rank': 1
    #         })

    #         request.env['customer.password'].sudo().create({
    #             'partner_id': customer.id,
    #             'password_hash': request.env['customer.password']._pwd_context.hash(password)
    #         })

    #         payload = {
    #             'user_id': customer.id,
    #             'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=2)
    #         }
    #         token = jwt.encode(payload, 'testing', algorithm='HS256')

    #         return {
    #             "status": "success",
    #             "message": "Registrazione completata con successo",
    #             "user": {
    #                 'name': customer.name,
    #                 'email': customer.email,
    #                 'company_id': customer.company_id.id if customer.company_id else False,
    #                 'lang': customer.lang or 'en_US'
    #             },
    #             "token": token if isinstance(token, str) else token.decode('utf-8')
    #         }

    #     except Exception as e:
    #         _logger.error('Registration error: %s', str(e))
    #         return {"status": "error", "message": "Errore del server"}
   