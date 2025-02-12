# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request, Response
import json
from odoo.tools import float_round
import logging

_logger = logging.getLogger(__name__)

class ProductAPI(http.Controller):
    
    def _get_product_price(self, product, pricelist, customer):
        """Calculate final price for product considering pricelist rules"""
        try:
            # First get the base list price
            base_price = product.list_price

            # Get applicable pricelist items
            pricelist_items = request.env['product.pricelist.item'].sudo().search([
                ('pricelist_id', '=', pricelist.id),
                
                # Filter by product
                '|', ('product_tmpl_id', '=', product.id), ('product_id', '=', product.id),
            ])
            print(pricelist_items,"-------------------pricelist_items-------------------")

            if not pricelist_items:
                return {
                    'final_price': base_price,
                    'min_quantity': 1,
                    'discount': 0
                }

            # Get the first applicable rule (ordered by min_quantity)
            rule = pricelist_items[0]
            final_price = base_price
            discount = 0

            # Calculate price based on compute_price method
            if rule.compute_price == 'fixed':
                final_price = rule.fixed_price
            elif rule.compute_price == 'percentage':
                discount = rule.percent_price
                final_price = base_price * (1 - (discount / 100.0))

            return {
                'final_price': float_round(final_price, precision_digits=2),
                'min_quantity': rule.min_quantity or 1,
                'discount': discount
            }

        except Exception as e:
            _logger.error(f"Error calculating price for product {product.id}: {str(e)}")
            return {
                'final_price': product.list_price,
                'min_quantity': 1,
                'discount': 0
            }

    @http.route('/api/v1/customer/products', type='json', auth='public', methods=['POST'], csrf=False)
    def get_customer_products(self, **kwargs):
        try:
            # Get request data
            data = json.loads(request.httprequest.data.decode('utf-8'))
            customer_id = data.get('customer_id')
            
            if not customer_id:
                return {'error': 'Customer ID is required'}, 400

            # Find customer using external import ID
            external_customer = request.env['res.partner'].sudo().search([
                ('id', '=', int(customer_id))
            ], limit=1)
            
            if not external_customer:
                return {'error': 'Customer not found'}, 404

            customer = external_customer
            if not customer:
                return {'error': 'Customer not found'}, 404

            # Get customer's pricelist
            pricelist = customer.property_product_pricelist
            if not pricelist:
                return {'error': 'No pricelist found for customer'}, 404

            # Get all active products
            products = request.env['product.template'].sudo().search([
                ('active', '=', True),
                ('sale_ok', '=', True)
            ])

            product_list = []
            for product in products:
                # Calculate price info
                price_info = self._get_product_price(product, pricelist, customer)
                # print(price_info,"--------------------price info----------------------")
                
                # Get product category info
                category = product.categ_id
                category_external_id = category.external_id if hasattr(category, 'external_id') else None

                product_data = {
                    'name': product.name,
                    'list_price': price_info['final_price'],  # Using calculated price
                    'standard_price': product.list_price,  # Original list price
                    'active': product.active,
                    'barcode': product.barcode or '',
                    'color': product.color if hasattr(product, 'color') else 0,
                    'id': product.id,
                    'external_id': product.external_id,  # Added external_id
                    'quantity': price_info['min_quantity'],
                    'is_published': product.is_published if hasattr(product, 'is_published') else False,
                    'rewards_score': product.rewards_score if hasattr(product, 'rewards_score') else 0,
                    'default_code': product.default_code or '',
                    'code': product.default_code or '',  # Using default_code as code
                    'category_id': category.id,
                    'category_name': category.name,
                    'category_external_id': category_external_id,
                    'price_info': {
                        'base_price': product.list_price,
                        'final_price': price_info['final_price'],
                        'discount': price_info['discount'],
                        'min_quantity': price_info['min_quantity'],
                        'currency': pricelist.currency_id.name,
                    }
                }
                product_list.append(product_data)

            return {
                'status': 'success',
                'customer': {
                    'id': customer.id,
                    'name': customer.name,
                    'pricelist': {
                        'id': pricelist.id,
                        'external_id': pricelist.external_id,
                        'name': pricelist.name,
                        'currency': pricelist.currency_id.name
                    }
                },
                'total_products': len(product_list),
                'products': product_list
            }

        except Exception as e:
            _logger.error(f"API Error: {str(e)}")
            return {'error': str(e)}, 500