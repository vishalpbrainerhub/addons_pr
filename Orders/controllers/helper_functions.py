import json
from odoo import http, fields, _
from odoo.http import request, Response
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

import json
from odoo import http, fields, _
from odoo.http import request, Response
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class ProductPriceController(http.Controller):
    
    @staticmethod
    def calculate_price_product(product_id, quantity, partner_id):
        """
        Calculate product price based on quantity. Handles both product-specific 
        and category-based pricelist items.
        
        Args:
            product_id (int): Product ID (can be product.product or product.template)
            quantity (float): Quantity of product
            partner_id (int): Partner ID for pricelist lookup
        """
        try:
            # Get product
            env = request.env
            product = env['product.template'].sudo().browse(product_id)
            # If product not found, try getting from template
            # if not product:
            #     template = env['product.template'].sudo().browse(product_id)
            #     if template:
            #         product = template.product_variant_id
            
            if not product:
                return 0
            
            # Get partner's pricelist
            partner = env['res.partner'].sudo().browse(partner_id)
            if not partner:
                return product.list_price
                
            price_list = partner.property_product_pricelist
            if not price_list:
                return product.list_price
            

            # Get matching pricelist items for both product and category
            price_rules = []
            base_price = product.list_price
            for item in price_list.item_ids:
                
                
                if (item.product_tmpl_id.id ==  product.id):
                    print("coming here")
                    price = 0
                    if item.compute_price == 'fixed':
                        price = item.fixed_price
                    elif item.compute_price == 'percentage':
                        price = item.percent_price
                    elif item.compute_price == 'formula':
                        price = base_price * (1 - (item.price_discount / 100))
                    
                    price_rules.append({
                        'min_quantity': item.min_quantity,
                        'price': price,
                        'applied_on': 'product'
                    })
                
                # Check for category-based rules
                elif item.categ_id == product.categ_id:
                    price = 0
                    if item.compute_price == 'fixed':
                        price = item.fixed_price
                    elif item.compute_price == 'percentage':
                        price = item.percent_price
                    elif item.compute_price == 'formula':
                        price = base_price * (1 - (item.price_discount / 100))
                    
                    price_rules.append({
                        'min_quantity': 0,  # Category rules don't typically have min quantity
                        'price': price,
                        'applied_on': 'category',
                    })
                    
                continue

            if not price_rules:
                return base_price
            
            print("price_rules", price_rules)
            # Sort rules by sequence and min_quantity
            # Product-specific rules take precedence over category rules
            sorted_rules = sorted(
                price_rules, 
                key=lambda x: (
                    -x['min_quantity']  # Higher quantities first
                )
            )
            
            
            # For product-specific rules, check quantity requirements
            product_rules = [r for r in sorted_rules]
            if product_rules:
                for rule in product_rules:
                    if quantity >= rule['min_quantity']:
                        return rule['price']
                return product_rules[-1]['price']  # Return price with lowest min_quantity
            
            # If no product-specific rules match, use category rule if exists
            category_rules = [r for r in sorted_rules if r['applied_on'] == 'category']
            if category_rules:
                return category_rules[0]['price']
            
            return base_price
        
        except Exception as e:
            _logger.error(f"Error calculating price: {str(e)}")
            return base_price