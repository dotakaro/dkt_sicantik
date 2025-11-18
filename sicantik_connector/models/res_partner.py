# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
import re


class ResPartner(models.Model):
    """
    Extend Partner model for WhatsApp integration
    """
    _inherit = 'res.partner'
    
    # WhatsApp Fields
    whatsapp_number = fields.Char(
        string='WhatsApp Number',
        help='WhatsApp number for notifications (format: +62xxx)'
    )
    
    def _get_mobile_or_phone(self):
        """
        Safe method to get mobile or phone number
        Di Odoo 18.4, field 'phone' selalu tersedia di res.partner (contact)
        
        Returns phone (prioritas utama), otherwise mobile, otherwise whatsapp_number, otherwise False
        
        Note: This method uses safe access (getattr) to avoid AttributeError
        if fields don't exist in database or model definition.
        """
        self.ensure_one()
        
        # Prioritas 1: phone (selalu tersedia di Odoo 18.4)
        phone_value = getattr(self, 'phone', None)
        if phone_value:
            return phone_value
        
        # Prioritas 2: mobile (jika tersedia)
        mobile_value = getattr(self, 'mobile', None)
        if mobile_value:
            return mobile_value
        
        # Prioritas 3: whatsapp_number (custom field)
        if hasattr(self, 'whatsapp_number') and self.whatsapp_number:
            return self.whatsapp_number
        
        return False
    
    whatsapp_opt_in = fields.Boolean(
        string='WhatsApp Notifications',
        default=False,
        help='Allow WhatsApp notifications for this contact'
    )
    
    whatsapp_opt_in_date = fields.Datetime(
        string='Opt-in Date',
        readonly=True,
        help='Date when contact opted in for WhatsApp notifications'
    )
    
    # SICANTIK Integration
    sicantik_permit_ids = fields.One2many(
        'sicantik.permit',
        'partner_id',
        string='SICANTIK Permits',
        help='Permits associated with this contact'
    )
    
    sicantik_permit_count = fields.Integer(
        string='Permit Count',
        compute='_compute_sicantik_permit_count',
        help='Number of permits for this contact'
    )
    
    @api.depends('sicantik_permit_ids')
    def _compute_sicantik_permit_count(self):
        """Compute permit count"""
        for partner in self:
            partner.sicantik_permit_count = len(partner.sicantik_permit_ids)
    
    @api.constrains('whatsapp_number')
    def _check_whatsapp_number(self):
        """Validate WhatsApp number format"""
        for partner in self:
            if partner.whatsapp_number:
                # Remove spaces and special characters
                number = re.sub(r'[^\d+]', '', partner.whatsapp_number)
                
                # Check format
                if not number.startswith('+'):
                    raise ValidationError(
                        'WhatsApp number must start with country code (e.g., +62 for Indonesia)'
                    )
                
                if len(number) < 10:
                    raise ValidationError(
                        'WhatsApp number is too short'
                    )
                
                # Update with cleaned format
                if number != partner.whatsapp_number:
                    partner.whatsapp_number = number
    
    def action_opt_in_whatsapp(self):
        """Opt-in for WhatsApp notifications"""
        self.ensure_one()
        
        if not self.whatsapp_number:
            raise ValidationError('Please set WhatsApp number first')
        
        self.write({
            'whatsapp_opt_in': True,
            'whatsapp_opt_in_date': fields.Datetime.now()
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'WhatsApp Notifications Enabled',
                'message': f'Notifications will be sent to {self.whatsapp_number}',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_opt_out_whatsapp(self):
        """Opt-out from WhatsApp notifications"""
        self.ensure_one()
        
        self.write({
            'whatsapp_opt_in': False
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'WhatsApp Notifications Disabled',
                'message': 'You will no longer receive WhatsApp notifications',
                'type': 'info',
                'sticky': False,
            }
        }
    
    def action_view_permits(self):
        """View permits for this contact"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Permits: {self.name}',
            'res_model': 'sicantik.permit',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }

