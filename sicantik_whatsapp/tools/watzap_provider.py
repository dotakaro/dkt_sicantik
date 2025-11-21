# -*- coding: utf-8 -*-

"""
Watzap.id Provider Implementation

API Documentation: https://api-docs.watzap.id
Base URL: https://api.watzap.id/v1
"""

import requests
import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class WatzapProvider:
    """
    Implementation untuk Watzap.id WhatsApp Gateway
    """
    
    def __init__(self, api_key, device_id, base_url='https://api.watzap.id/v1'):
        """
        Initialize Watzap provider
        
        Args:
            api_key (str): API key dari dashboard Watzap.id
            device_id (str): Device/Sender ID
            base_url (str): Base URL API (default: https://api.watzap.id/v1)
        """
        self.api_key = api_key
        self.device_id = device_id
        self.base_url = base_url.rstrip('/')
        self.timeout = 30
    
    def _get_headers(self):
        """
        Get HTTP headers untuk request
        
        Returns:
            dict: Headers
        """
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
    
    def send_template(self, phone_number, template_id, parameters, language='id'):
        """
        Kirim template message via Watzap.id API
        
        Args:
            phone_number (str): Nomor HP penerima (format: 6281234567890)
            template_id (str): Template ID dari Watzap.id
            parameters (dict): Parameter values dengan format {"1": "value1", "2": "value2", ...}
            language (str): Kode bahasa (default: 'id')
        
        Returns:
            dict: Response dari API
        """
        # Normalize phone number
        phone = self._normalize_phone(phone_number)
        
        # Prepare payload
        payload = {
            'phone': phone,
            'template_id': template_id,
            'language': language,
            'parameters': parameters
        }
        
        _logger.info(f'📤 Watzap.id: Sending template {template_id} to {phone}')
        _logger.debug(f'   Payload: {payload}')
        
        try:
            url = f'{self.base_url}/message/sendTemplate'
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
            
            if result.get('status') == 'success' or result.get('success'):
                _logger.info(f'✅ Watzap.id: Message sent successfully')
                return {
                    'success': True,
                    'message_id': result.get('message_id') or result.get('id'),
                    'response': result
                }
            else:
                error_msg = result.get('message') or result.get('error') or 'Unknown error'
                _logger.error(f'❌ Watzap.id: {error_msg}')
                return {
                    'success': False,
                    'error': error_msg,
                    'response': result
                }
                
        except requests.exceptions.RequestException as e:
            error_msg = f'Request error: {str(e)}'
            _logger.error(f'❌ Watzap.id: {error_msg}')
            return {
                'success': False,
                'error': error_msg
            }
        except Exception as e:
            error_msg = f'Unexpected error: {str(e)}'
            _logger.error(f'❌ Watzap.id: {error_msg}', exc_info=True)
            return {
                'success': False,
                'error': error_msg
            }
    
    def send_text(self, phone_number, message):
        """
        Kirim pesan teks bebas (bukan template)
        
        Args:
            phone_number (str): Nomor HP penerima
            message (str): Teks pesan
        
        Returns:
            dict: Response dari API
        """
        phone = self._normalize_phone(phone_number)
        
        payload = {
            'phone': phone,
            'message': message
        }
        
        _logger.info(f'📤 Watzap.id: Sending text to {phone}')
        
        try:
            url = f'{self.base_url}/message/sendText'
            response = requests.post(
                url,
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout
            )
            
            response.raise_for_status()
            result = response.json()
            
            if result.get('status') == 'success' or result.get('success'):
                _logger.info(f'✅ Watzap.id: Text sent successfully')
                return {
                    'success': True,
                    'message_id': result.get('message_id') or result.get('id'),
                    'response': result
                }
            else:
                error_msg = result.get('message') or 'Unknown error'
                _logger.error(f'❌ Watzap.id: {error_msg}')
                return {
                    'success': False,
                    'error': error_msg,
                    'response': result
                }
                
        except Exception as e:
            error_msg = f'Error sending text: {str(e)}'
            _logger.error(f'❌ Watzap.id: {error_msg}')
            return {
                'success': False,
                'error': error_msg
            }
    
    def check_status(self, message_id):
        """
        Cek status pengiriman pesan
        
        Args:
            message_id (str): Message ID dari Watzap.id
        
        Returns:
            dict: Status message
        """
        try:
            url = f'{self.base_url}/message/status/{message_id}'
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=self.timeout
            )
            
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            _logger.error(f'Error checking Watzap status: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }
    
    def _normalize_phone(self, phone):
        """
        Normalize nomor HP ke format internasional tanpa + dan spasi
        
        Args:
            phone (str): Nomor HP input
        
        Returns:
            str: Nomor ternormalisasi (e.g., 6281234567890)
        """
        if not phone:
            raise UserError('Nomor HP tidak boleh kosong')
        
        # Remove whitespace, dash, parentheses
        phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        
        # Remove + if exists
        if phone.startswith('+'):
            phone = phone[1:]
        
        # Convert 0xxx to 62xxx untuk Indonesia
        if phone.startswith('0'):
            phone = '62' + phone[1:]
        
        # Ensure starts with country code
        if not phone.startswith('62'):
            phone = '62' + phone
        
        return phone

