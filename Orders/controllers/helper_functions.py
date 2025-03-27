from odoo import http, fields
from odoo.http import request, Response
import json
import logging

_logger = logging.getLogger(__name__)

class ProductPriceController(http.Controller):    
    
    @staticmethod
    def calculate_price_product(product_id, quantity, partner_id):
        """
        Calculate product price based on quantity. Handles both product-specific 
        and category-based pricelist items.
        
        Args:
            product_id (int): Product ID (product.template)
            quantity (float): Quantity of product
            partner_id (int): Partner ID for pricelist lookup
        
        Returns:
            float: The calculated price
        """
        try:
            # Get product
            env = request.env
            product = env['product.template'].sudo().browse(product_id)
            
            if not product:
                return 0
            
            # Get partner's pricelist using ORM
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
                price = 0
                
                # Product-specific rule
                if item.product_tmpl_id.id == product.id:
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
                
                # Category-based rule
                elif item.categ_id.id == product.categ_id.id:
                    if item.compute_price == 'fixed':
                        price = item.fixed_price
                    elif item.compute_price == 'percentage':
                        price = item.percent_price
                    elif item.compute_price == 'formula':
                        price = base_price * (1 - (item.price_discount / 100))
                    
                    price_rules.append({
                        'min_quantity': item.min_quantity,
                        'price': price,
                        'applied_on': 'category',
                    })
            print(price_rules,"-------------------pricerules-------------")
            if not price_rules:
                return base_price
            
            # Sort rules by min_quantity (descending)
            # Product-specific rules take precedence over category rules
            sorted_rules = sorted(
                price_rules, 
                key=lambda x: (
                    0 if x['applied_on'] == 'product' else 1,  # Product rules first
                    -x['min_quantity']  # Higher quantities first
                )
            )
            
            # Find the first rule that matches the quantity
            for rule in sorted_rules:
                if quantity >= rule['min_quantity']:
                    return rule['price']
            
            # If no rule matches, return the base price
            return base_price
        
        except Exception as e:
            _logger.error(f"Error calculating price: {str(e)}")
            return base_price
    
    @staticmethod
    def get_min_quantity_price(product_id, partner_id):
        """
        Get the price associated with the minimum quantity rule for a product.
        
        Args:
            product_id (int): Product ID (product.template)
            partner_id (int): Partner ID for pricelist lookup
        
        Returns:
            dict: Dictionary containing price, minimum quantity, and all price rules
        """
        try:
            # Get product
            env = request.env
            product = env['product.template'].sudo().browse(product_id)
            
            if not product:
                return {'price': 0, 'min_quantity': 0, 'price_rules': []}
            
            # Get partner's pricelist using ORM
            partner = env['res.partner'].sudo().browse(partner_id)
            if not partner:
                return {'price': product.list_price, 'min_quantity': 0, 'price_rules': []}
                
            price_list = partner.property_product_pricelist
            if not price_list:
                return {'price': product.list_price, 'min_quantity': 0, 'price_rules': []}
            
            # Get matching pricelist items for both product and category
            price_rules = []
            base_price = product.list_price
            
            for item in price_list.item_ids:
                price = 0
                
                # Product-specific rule
                if item.product_tmpl_id.id == product.id:
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
                
                # Category-based rule
                elif item.categ_id.id == product.categ_id.id:
                    if item.compute_price == 'fixed':
                        price = item.fixed_price
                    elif item.compute_price == 'percentage':
                        price = item.percent_price
                    elif item.compute_price == 'formula':
                        price = base_price * (1 - (item.price_discount / 100))
                    
                    price_rules.append({
                        'min_quantity': item.min_quantity,
                        'price': price,
                        'applied_on': 'category',
                    })
            
            if not price_rules:
                return {'price': base_price, 'min_quantity': 0, 'price_rules': []}
            
            # Sort rules by min_quantity (ascending)
            # Product-specific rules take precedence over category rules
            sorted_rules = sorted(
                price_rules, 
                key=lambda x: (
                    0 if x['applied_on'] == 'product' else 1,  # Product rules first
                    x['min_quantity']  # Lower quantities first (ascending)
                )
            )
            
            # Get the price for the minimum quantity (first rule after sorting)
            min_rule = sorted_rules[0]
            
            return {
                'price': min_rule['price'],
                'min_quantity': min_rule['min_quantity'],
                'price_rules': sorted_rules
            }
        
        except Exception as e:
            _logger.error(f"Error getting min quantity price: {str(e)}")
            return {'price': product.list_price, 'min_quantity': 0, 'price_rules': []}