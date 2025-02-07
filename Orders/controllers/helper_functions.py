import json
from odoo import http, fields, _
from odoo.http import request, Response
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class ProductPriceController(http.Controller):
    
    def _get_customer_by_email(self, email):
        """Get customer record by email"""
        if not email:
            return False
            
        Partner = request.env['res.partner'].sudo()
        partner = Partner.search([
            ('email', '=', email),
            ('active', '=', True)
        ], limit=1)
        
        return partner
    
    def _get_product_pricelist(self, partner):
        """Get appropriate pricelist for the customer"""
        Pricelist = request.env['product.pricelist'].sudo()
        
        if partner and partner.property_product_pricelist:
            return partner.property_product_pricelist
        
        # Default to public pricelist if no customer-specific one found
        return Pricelist.search([('name', '=', 'Public Pricelist')], limit=1)
    
    def _get_product_price_data(self, product, pricelist, quantity=1.0, partner=None):
        """
        Calculate product price based on pricelist and quantity
        Returns prices and related information
        """
        try:
            # Set context for price computation
            product = product.with_context(
                quantity=quantity,
                pricelist=pricelist.id,
                partner=partner.id if partner else None
            )
            
            # Get base price
            base_price = product.list_price
            
            # Get pricelist price
            pricelist_price = pricelist.get_product_price(
                product, 
                quantity,
                partner
            )
            
            # Get quantity breaks if any
            quantity_breaks = []
            if product.item_ids:
                for item in product.item_ids:
                    if item.min_quantity > 0:
                        item_price = pricelist.get_product_price(
                            product,
                            item.min_quantity,
                            partner
                        )
                        quantity_breaks.append({
                            'min_quantity': item.min_quantity,
                            'price': item_price
                        })
            
            return {
                'base_price': base_price,
                'pricelist_price': pricelist_price,
                'final_price': pricelist_price,
                'currency': pricelist.currency_id.name,
                'pricelist_name': pricelist.name,
                'quantity_breaks': sorted(quantity_breaks, key=lambda x: x['min_quantity']),
                'min_quantity': product.min_quantity or 1.0,
                'has_special_price': abs(base_price - pricelist_price) > 0.01
            }
            
        except Exception as e:
            _logger.error(f"Error calculating price for product {product.id}: {str(e)}")
            return None

    @http.route(['/api/v1/products/pricelist'], 
                type='http', auth='public', methods=['GET'], csrf=False)
    def get_products_with_pricelist(self, **kwargs):
        try:
            # Get query parameters
            email = kwargs.get('email')
            quantity = float(kwargs.get('quantity', 1.0))
            product_ids = kwargs.get('product_ids')
            
            # Get customer and their pricelist
            partner = self._get_customer_by_email(email)
            pricelist = self._get_product_pricelist(partner)
            
            # Build product domain
            domain = [('active', '=', True)]
            if product_ids:
                product_ids = [int(pid) for pid in product_ids.split(',')]
                domain.append(('id', 'in', product_ids))
            
            # Get products
            Product = request.env['product.template'].sudo()
            products = Product.search(domain)
            
            product_data = []
            for product in products:
                price_info = self._get_product_price_data(product, pricelist, quantity, partner)
                if price_info:
                    product_data.append({
                        'id': product.id,
                        'name': product.name,
                        'sku': product.default_code or '',
                        'code_': product.code_ or '',
                        'quantity': quantity,
                        'prices': price_info,
                        'uom': product.uom_id.name,
                        'category': product.categ_id.name,
                        'external_id': product.external_import_id or '',
                    })
            
            return Response(
                json.dumps({
                    'success': True,
                    'customer': {
                        'id': partner.id if partner else None,
                        'name': partner.name if partner else None,
                        'pricelist': pricelist.name,
                        'pricelist_id': pricelist.id,
                    },
                    'products': product_data,
                    'timestamp': fields.Datetime.now()
                }), 
                content_type='application/json'
            )

        except Exception as e:
            _logger.error(f"Error processing request: {str(e)}")
            return Response(
                json.dumps({
                    'success': False,
                    'error': str(e)
                }), 
                content_type='application/json',
                status=500
            )
            
    @http.route(['/api/v1/product/price'], 
                type='http', auth='public', methods=['GET'], csrf=False)
    def get_single_product_price(self, **kwargs):
        try:
            # Get parameters
            product_id = int(kwargs.get('product_id', 0))
            email = kwargs.get('email')
            quantity = float(kwargs.get('quantity', 1.0))
            
            if not product_id:
                raise ValidationError(_('Product ID is required'))
            
            # Get customer and pricelist    
            partner = self._get_customer_by_email(email)
            pricelist = self._get_product_pricelist(partner)
                
            # Get product
            Product = request.env['product.template'].sudo()
            product = Product.browse(product_id)
            
            if not product.exists():
                return Response(
                    json.dumps({
                        'success': False,
                        'error': 'Product not found'
                    }), 
                    content_type='application/json',
                    status=404
                )
            
            price_info = self._get_product_price_data(product, pricelist, quantity, partner)
            
            return Response(
                json.dumps({
                    'success': True,
                    'customer': {
                        'id': partner.id if partner else None,
                        'name': partner.name if partner else None,
                        'pricelist': pricelist.name,
                        'pricelist_id': pricelist.id,
                    },
                    'product': {
                        'id': product.id,
                        'name': product.name,
                        'sku': product.default_code or '',
                        'code_': product.code_ or '',
                        'quantity': quantity,
                        'prices': price_info,
                        'uom': product.uom_id.name,
                        'category': product.categ_id.name,
                        'external_id': product.external_import_id or '',
                    }
                }), 
                content_type='application/json'
            )
                
        except Exception as e:
            _logger.error(f"Error processing request: {str(e)}")
            return Response(
                json.dumps({
                    'success': False,
                    'error': str(e)
                }), 
                content_type='application/json',
                status=500
            )