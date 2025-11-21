# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class WhatsAppDispatcher(models.AbstractModel):
    """
    Service untuk routing pesan WhatsApp ke provider yang tepat.
    
    Logic routing:
    1. Cek opt-in status partner untuk Meta
    2. Pilih provider sesuai kondisi
    3. Format parameter sesuai provider
    4. Kirim via provider implementation
    """
    _name = 'sicantik.whatsapp.dispatcher'
    _description = 'WhatsApp Message Dispatcher'
    
    def determine_provider(self, partner_id, permit_id=None):
        """
        Tentukan provider yang akan digunakan untuk mengirim pesan
        
        Args:
            partner_id (int): ID partner penerima
            permit_id (int, optional): ID permit terkait
        
        Returns:
            dict: {
                'provider': sicantik.whatsapp.provider object,
                'reason': str (alasan pemilihan provider),
                'use_24h_window': bool (untuk Meta)
            }
        """
        partner = self.env['res.partner'].browse(partner_id)
        
        if not partner:
            raise UserError('Partner tidak ditemukan')
        
        # Get default provider dari config
        default_provider_id = self.env['ir.config_parameter'].sudo().get_param(
            'sicantik_whatsapp.default_provider_id'
        )
        
        if not default_provider_id:
            raise UserError(
                'Default provider belum dikonfigurasi.\n\n'
                'Silakan set provider default di Settings → General Settings → WhatsApp Notifications'
            )
        
        default_provider = self.env['sicantik.whatsapp.provider'].browse(int(default_provider_id))
        
        if not default_provider or not default_provider.active:
            raise UserError('Default provider tidak valid atau tidak aktif')
        
        # Jika provider Meta, cek opt-in status
        if default_provider.provider_type == 'meta':
            # Cek opt-in + 24h window
            opt_in_manager = self.env['whatsapp.opt.in.manager']
            
            if not default_provider.meta_account_id:
                raise UserError(
                    f'Provider "{default_provider.name}" belum dikonfigurasi Meta Account.\n\n'
                    f'Silakan set Meta Account di menu WhatsApp → Konfigurasi → Profil Provider'
                )
            
            can_send = opt_in_manager.check_can_send_template(
                partner_id,
                default_provider.meta_account_id.id
            )
            
            if can_send['can_send']:
                return {
                    'provider': default_provider,
                    'reason': 'Meta (opt-in aktif)' if can_send.get('opt_in_status') else 'Meta (24h window)',
                    'use_24h_window': can_send.get('use_24h_window', False),
                }
            else:
                # Meta tidak bisa kirim, cari fallback provider (Watzap/Fonnte)
                fallback = self.env['sicantik.whatsapp.provider'].search([
                    ('provider_type', 'in', ['watzap', 'fonnte']),
                    ('active', '=', True),
                    ('credential_state', '=', 'configured')
                ], limit=1, order='sequence ASC')
                
                if not fallback:
                    raise UserError(
                        f'Partner {partner.name} belum opt-in Meta dan tidak ada fallback provider aktif.\n\n'
                        f'Solusi:\n'
                        f'1. Minta partner mengirim pesan ke WhatsApp Business Account, atau\n'
                        f'2. Aktifkan provider fallback (Watzap.id atau Fonnte)'
                    )
                
                _logger.info(
                    f'Meta tidak bisa kirim ke {partner.name} ({can_send["reason"]}). '
                    f'Fallback ke {fallback.name}'
                )
                
                return {
                    'provider': fallback,
                    'reason': f'{fallback.provider_type.title()} (fallback, Meta opt-in required)',
                    'use_24h_window': False,
                }
        else:
            # Provider bukan Meta (Watzap/Fonnte), langsung gunakan
            return {
                'provider': default_provider,
                'reason': f'{default_provider.provider_type.title()} (default)',
                'use_24h_window': False,
            }
    
    def send_template_message(self, template_key, partner_id, context_values, permit_id=None):
        """
        Kirim template message via provider yang sesuai
        
        Args:
            template_key (str): Template key dari sicantik.whatsapp.template.master
            partner_id (int): ID partner penerima
            context_values (dict): Dictionary nilai untuk parameter template
            permit_id (int, optional): ID permit terkait
        
        Returns:
            dict: {
                'success': bool,
                'provider': provider name,
                'message_id': ID pesan (jika sukses),
                'error': error message (jika gagal)
            }
        """
        # Get master template
        master_template = self.env['sicantik.whatsapp.template.master'].search([
            ('template_key', '=', template_key),
            ('active', '=', True)
        ], limit=1)
        
        if not master_template:
            raise UserError(f'Template dengan key "{template_key}" tidak ditemukan')
        
        # Determine provider
        routing = self.determine_provider(partner_id, permit_id)
        provider = routing['provider']
        
        _logger.info(
            f'📤 Sending template "{template_key}" via {provider.name}: {routing["reason"]}'
        )
        
        # Get provider-specific template
        provider_template = master_template.get_provider_template(provider.provider_type)
        
        if provider_template['status'] not in ['configured', 'approved']:
            raise UserError(
                f'Template "{template_key}" belum dikonfigurasi untuk provider {provider.name}.\n\n'
                f'Status: {provider_template["status"]}'
            )
        
        # Kirim via provider implementation
        try:
            if provider.provider_type == 'meta':
                result = self._send_via_meta(
                    provider,
                    provider_template,
                    partner_id,
                    context_values,
                    master_template
                )
            elif provider.provider_type == 'watzap':
                result = self._send_via_watzap(
                    provider,
                    provider_template,
                    partner_id,
                    context_values,
                    master_template
                )
            elif provider.provider_type == 'fonnte':
                result = self._send_via_fonnte(
                    provider,
                    provider_template,
                    partner_id,
                    context_values,
                    master_template
                )
            else:
                raise UserError(f'Provider type tidak didukung: {provider.provider_type}')
            
            # Increment usage counter
            if result.get('success'):
                master_template.increment_usage()
            
            return result
            
        except Exception as e:
            _logger.error(f'Error sending template via {provider.name}: {str(e)}', exc_info=True)
            return {
                'success': False,
                'provider': provider.name,
                'error': str(e)
            }
    
    def _send_via_meta(self, provider, provider_template, partner_id, context_values, master_template):
        """
        Kirim via Meta Official API (menggunakan modul Odoo Enterprise)
        
        Returns:
            dict: Result dictionary
        """
        partner = self.env['res.partner'].browse(partner_id)
        
        if not provider_template['template_obj']:
            raise UserError(
                f'Template Meta belum di-link. Gunakan tombol "Sync from Meta" di master template.'
            )
        
        meta_template = provider_template['template_obj']
        
        # TODO: Implement actual Meta sending via whatsapp.composer
        # Untuk sekarang, return placeholder
        _logger.warning('Meta sending not yet implemented, returning placeholder')
        
        return {
            'success': True,
            'provider': provider.name,
            'message_id': 'meta_placeholder_id',
            'note': 'Meta integration pending (Task 4)'
        }
    
    def _send_via_watzap(self, provider, provider_template, partner_id, context_values, master_template):
        """
        Kirim via Watzap.id API
        
        Returns:
            dict: Result dictionary
        """
        from odoo.addons.sicantik_whatsapp.tools.watzap_provider import WatzapProvider
        from odoo.addons.sicantik_whatsapp.tools.parameter_converter import ParameterConverter
        
        partner = self.env['res.partner'].browse(partner_id)
        
        # Validate credentials
        if not provider.watzap_api_key or not provider.watzap_device_id:
            raise UserError(
                f'Provider "{provider.name}" belum dikonfigurasi dengan lengkap.\n\n'
                f'Silakan set API Key dan Device ID di menu WhatsApp → Konfigurasi → Profil Provider'
            )
        
        # Get phone number
        mobile = partner._get_mobile_or_phone()
        if not mobile:
            raise UserError(f'Partner {partner.name} tidak memiliki nomor WhatsApp')
        
        # Validate parameters
        param_list = master_template.get_parameter_list()
        is_valid, missing = ParameterConverter.validate_context_values(param_list, context_values)
        
        if not is_valid:
            _logger.warning(f'Missing parameters: {missing}. Continuing with available values.')
        
        # Convert parameters ke format Watzap
        watzap_params = ParameterConverter.generic_to_watzap(param_list, context_values)
        
        # Initialize provider
        watzap = WatzapProvider(
            api_key=provider.watzap_api_key,
            device_id=provider.watzap_device_id,
            base_url=provider.watzap_base_url or 'https://api.watzap.id/v1'
        )
        
        # Send message
        result = watzap.send_template(
            phone_number=mobile,
            template_id=provider_template['template_id'] or provider_template['template_name'],
            parameters=watzap_params['parameters'],
            language=master_template.language or 'id'
        )
        
        if result['success']:
            return {
                'success': True,
                'provider': provider.name,
                'message_id': result.get('message_id'),
            }
        else:
            return {
                'success': False,
                'provider': provider.name,
                'error': result.get('error'),
            }
    
    def _send_via_fonnte(self, provider, provider_template, partner_id, context_values, master_template):
        """
        Kirim via Fonnte API
        
        Returns:
            dict: Result dictionary
        """
        from odoo.addons.sicantik_whatsapp.tools.fonnte_provider import FonnteProvider
        from odoo.addons.sicantik_whatsapp.tools.parameter_converter import ParameterConverter
        
        partner = self.env['res.partner'].browse(partner_id)
        
        # Validate credentials
        if not provider.fonnte_token:
            raise UserError(
                f'Provider "{provider.name}" belum dikonfigurasi dengan lengkap.\n\n'
                f'Silakan set API Token di menu WhatsApp → Konfigurasi → Profil Provider'
            )
        
        # Get phone number
        mobile = partner._get_mobile_or_phone()
        if not mobile:
            raise UserError(f'Partner {partner.name} tidak memiliki nomor WhatsApp')
        
        # Validate parameters
        param_list = master_template.get_parameter_list()
        is_valid, missing = ParameterConverter.validate_context_values(param_list, context_values)
        
        if not is_valid:
            _logger.warning(f'Missing parameters: {missing}. Continuing with available values.')
        
        # Convert parameters ke format Fonnte
        fonnte_params = ParameterConverter.generic_to_fonnte(param_list, context_values)
        
        # Initialize provider
        fonnte = FonnteProvider(
            token=provider.fonnte_token,
            device=provider.fonnte_device or '',
            api_url=provider.fonnte_api_url or 'https://api.fonnte.com'
        )
        
        # Send message
        result = fonnte.send_template(
            phone_number=mobile,
            template_id=provider_template['template_id'] or provider_template['template_name'],
            parameters=fonnte_params
        )
        
        if result['success']:
            return {
                'success': True,
                'provider': provider.name,
                'message_id': result.get('message_id'),
            }
        else:
            return {
                'success': False,
                'provider': provider.name,
                'error': result.get('error'),
            }

