# -*- coding: utf-8 -*-

"""
Fonnte Provider Implementation

API Documentation: https://docs.fonnte.com
Base URL: https://api.fonnte.com
"""

import requests
import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class FonnteProvider:
    """
    Implementation untuk Fonnte WhatsApp Gateway
    """
    
    def __init__(self, token, device='', api_url='https://api.fonnte.com'):
        """
        Initialize Fonnte provider
        
        Args:
            token (str): API token dari Fonnte
            device (str): Device identifier (optional)
            api_url (str): Base URL API
        """
        self.token = token
        self.device = device
        self.api_url = api_url.rstrip('/')
        self.timeout = 30
    
    def _get_headers(self):
        """
        Get HTTP headers untuk request
        
        Returns:
            dict: Headers
        """
        return {
            'Authorization': self.token,
            'Content-Type': 'application/json',
        }
    
    def send_template(self, phone_number, template_id, parameters):
        """
        Kirim template message via Fonnte API
        
        Args:
            phone_number (str): Nomor HP penerima
            template_id (str): Template ID dari Fonnte
            parameters (dict): Parameter values dengan format {"var1": "value1", "var2": "value2", ...}
        
        Returns:
            dict: Response dari API
        """
        phone = self._normalize_phone(phone_number)
        
        # Prepare payload
        payload = {
            'target': phone,
            'template': template_id,
        }
        
        # Add parameters
        payload.update(parameters)
        
        # Add device if specified
        if self.device:
            payload['device'] = self.device
        
        _logger.info(f'📤 Fonnte: Sending template {template_id} to {phone}')
        _logger.debug(f'   Payload: {payload}')
        
        try:
            url = f'{self.api_url}/send'
            response = requests.post(
                url,
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout
            )
            
            _logger.info(f'   Response status: {response.status_code}')
            _logger.debug(f'   Response body: {response.text[:500]}')
            
            response.raise_for_status()
            result = response.json()
            
            if result.get('status'):
                _logger.info(f'✅ Fonnte: Message sent successfully')
                return {
                    'success': True,
                    'message_id': result.get('id') or result.get('message_id'),
                    'response': result
                }
            else:
                error_msg = result.get('reason') or 'Unknown error'
                _logger.error(f'❌ Fonnte: {error_msg}')
                return {
                    'success': False,
                    'error': error_msg,
                    'response': result
                }
                
        except requests.exceptions.RequestException as e:
            error_msg = f'Request error: {str(e)}'
            _logger.error(f'❌ Fonnte: {error_msg}')
            return {
                'success': False,
                'error': error_msg
            }
        except Exception as e:
            error_msg = f'Unexpected error: {str(e)}'
            _logger.error(f'❌ Fonnte: {error_msg}', exc_info=True)
            return {
                'success': False,
                'error': error_msg
            }
    
    def send_text(self, phone_number, message):
        """
        Kirim pesan teks bebas
        
        Args:
            phone_number (str): Nomor HP penerima
            message (str): Teks pesan
        
        Returns:
            dict: Response dari API
        """
        phone = self._normalize_phone(phone_number)
        
        payload = {
            'target': phone,
            'message': message,
        }
        
        if self.device:
            payload['device'] = self.device
        
        _logger.info(f'📤 Fonnte: Sending text to {phone}')
        
        try:
            url = f'{self.api_url}/send'
            response = requests.post(
                url,
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout
            )
            
            response.raise_for_status()
            result = response.json()
            
            if result.get('status'):
                _logger.info(f'✅ Fonnte: Text sent successfully')
                return {
                    'success': True,
                    'message_id': result.get('id'),
                    'response': result
                }
            else:
                error_msg = result.get('reason') or 'Unknown error'
                _logger.error(f'❌ Fonnte: {error_msg}')
                return {
                    'success': False,
                    'error': error_msg,
                    'response': result
                }
                
        except Exception as e:
            error_msg = f'Error sending text: {str(e)}'
            _logger.error(f'❌ Fonnte: {error_msg}')
            return {
                'success': False,
                'error': error_msg
            }
    
    def _normalize_phone(self, phone):
        """
        Normalize nomor HP ke format internasional
        
        Args:
            phone (str): Nomor HP input
        
        Returns:
            str: Nomor ternormalisasi (e.g., 6281234567890)
        """
        if not phone:
            raise UserError('Nomor HP tidak boleh kosong')
        
        phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        
        if phone.startswith('+'):
            phone = phone[1:]
        
        if phone.startswith('0'):
            phone = '62' + phone[1:]
        
        if not phone.startswith('62'):
            phone = '62' + phone
        
        return phone

