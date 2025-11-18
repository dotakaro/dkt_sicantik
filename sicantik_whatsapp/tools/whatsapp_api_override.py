# -*- coding: utf-8 -*-

import logging
import json
from odoo.addons.whatsapp.tools.whatsapp_api import WhatsAppApi

_logger = logging.getLogger(__name__)


class WhatsAppApiOverride(WhatsAppApi):
    """
    Override WhatsAppApi untuk menambahkan logging response API yang lebih detail
    """
    
    def _send_whatsapp(self, number, message_type, send_vals, parent_message_id=False):
        """
        Override untuk menambahkan logging response API
        """
        # Panggil method parent
        try:
            msg_uid = super()._send_whatsapp(number, message_type, send_vals, parent_message_id)
            _logger.info(f'✅ WhatsApp API Response: Message ID = {msg_uid}')
            return msg_uid
        except Exception as e:
            _logger.error(f'❌ WhatsApp API Error: {str(e)}')
            # Coba log response jika ada
            if hasattr(e, 'error_message'):
                _logger.error(f'   Error message: {e.error_message}')
            if hasattr(e, 'error_code'):
                _logger.error(f'   Error code: {e.error_code}')
            raise

