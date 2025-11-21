# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
import json

_logger = logging.getLogger(__name__)


class WhatsAppTemplateMaster(models.Model):
    """
    Master template yang kompatibel dengan berbagai provider.
    
    Template ini menyimpan:
    - Template key (ID internal)
    - Parameter list dengan placeholder generik
    - Mapping ke template ID masing-masing provider
    - Preview body template
    """
    _name = 'sicantik.whatsapp.template.master'
    _description = 'WhatsApp Master Template (Multi-Provider)'
    _rec_name = 'template_key'
    
    # Basic Info
    template_key = fields.Char(
        string='Template Key',
        required=True,
        help='ID internal untuk referensi template (e.g., permit_ready, permit_reminder)'
    )
    name = fields.Char(
        string='Template Name',
        required=True,
        help='Nama deskriptif template'
    )
    description = fields.Text(
        string='Description',
        help='Deskripsi fungsi template'
    )
    active = fields.Boolean(
        string='Active',
        default=True
    )
    
    # Template Content
    body_preview = fields.Text(
        string='Body Preview',
        required=True,
        help='Preview konten template dengan placeholder generik (e.g., {{partner_name}}, {{permit_number}})'
    )
    
    # Parameters
    parameter_list = fields.Text(
        string='Parameter List (JSON)',
        required=True,
        default='[]',
        help='List parameter dalam format JSON array, e.g., ["partner_name", "permit_number", "status"]'
    )
    parameter_count = fields.Integer(
        string='Parameter Count',
        compute='_compute_parameter_count',
        store=True
    )
    
    # Provider Mapping
    meta_template_id = fields.Many2one(
        'whatsapp.template',
        string='Meta Template',
        help='Template WhatsApp resmi dari Meta (Odoo Enterprise)'
    )
    meta_template_name = fields.Char(
        string='Meta Template Name',
        help='Nama template di Meta Console (fallback jika meta_template_id belum di-set)'
    )
    
    watzap_template_id = fields.Char(
        string='Watzap Template ID',
        help='Template ID dari dashboard Watzap.id'
    )
    watzap_template_name = fields.Char(
        string='Watzap Template Name',
        help='Nama template di Watzap.id'
    )
    
    fonnte_template_id = fields.Char(
        string='Fonnte Template ID',
        help='Template ID dari dashboard Fonnte'
    )
    fonnte_template_name = fields.Char(
        string='Fonnte Template Name',
        help='Nama template di Fonnte'
    )
    
    # Status per Provider
    meta_status = fields.Selection([
        ('not_configured', 'Not Configured'),
        ('configured', 'Configured'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Meta Status', default='not_configured')
    
    watzap_status = fields.Selection([
        ('not_configured', 'Not Configured'),
        ('configured', 'Configured'),
    ], string='Watzap Status', default='not_configured')
    
    fonnte_status = fields.Selection([
        ('not_configured', 'Not Configured'),
        ('configured', 'Configured'),
    ], string='Fonnte Status', default='not_configured')
    
    # Language
    language = fields.Selection([
        ('id', 'Bahasa Indonesia'),
        ('en', 'English'),
        ('id_ID', 'Bahasa Indonesia (id_ID)'),
        ('en_US', 'English (en_US)'),
    ], string='Language', default='id', required=True)
    
    # Usage Statistics
    usage_count = fields.Integer(
        string='Usage Count',
        readonly=True,
        help='Total penggunaan template'
    )
    last_used_date = fields.Datetime(
        string='Last Used',
        readonly=True
    )
    
    @api.depends('parameter_list')
    def _compute_parameter_count(self):
        for record in self:
            try:
                params = json.loads(record.parameter_list or '[]')
                record.parameter_count = len(params) if isinstance(params, list) else 0
            except:
                record.parameter_count = 0
    
    @api.constrains('template_key')
    def _check_template_key_unique(self):
        for record in self:
            if record.template_key:
                existing = self.search([
                    ('template_key', '=', record.template_key),
                    ('id', '!=', record.id)
                ])
                if existing:
                    raise ValidationError(
                        f'Template key "{record.template_key}" sudah digunakan oleh template lain: {existing.name}'
                    )
    
    @api.constrains('parameter_list')
    def _check_parameter_list_json(self):
        for record in self:
            if record.parameter_list:
                try:
                    params = json.loads(record.parameter_list)
                    if not isinstance(params, list):
                        raise ValueError('Parameter list harus berupa JSON array')
                except json.JSONDecodeError as e:
                    raise ValidationError(f'Parameter list bukan JSON valid: {str(e)}')
                except ValueError as e:
                    raise ValidationError(str(e))
    
    def get_parameter_list(self):
        """
        Get parameter list as Python list
        
        Returns:
            list: Parameter names
        """
        self.ensure_one()
        try:
            return json.loads(self.parameter_list or '[]')
        except:
            return []
    
    def get_provider_template(self, provider_type):
        """
        Get template ID/reference untuk provider tertentu
        
        Args:
            provider_type (str): 'meta', 'watzap', atau 'fonnte'
        
        Returns:
            dict: {
                'template_id': ID/name template,
                'status': status konfigurasi,
                'template_obj': object template (untuk Meta)
            }
        """
        self.ensure_one()
        
        if provider_type == 'meta':
            return {
                'template_id': self.meta_template_id.id if self.meta_template_id else None,
                'template_name': self.meta_template_name or (self.meta_template_id.template_name if self.meta_template_id else None),
                'status': self.meta_status,
                'template_obj': self.meta_template_id,
            }
        elif provider_type == 'watzap':
            return {
                'template_id': self.watzap_template_id,
                'template_name': self.watzap_template_name,
                'status': self.watzap_status,
                'template_obj': None,
            }
        elif provider_type == 'fonnte':
            return {
                'template_id': self.fonnte_template_id,
                'template_name': self.fonnte_template_name,
                'status': self.fonnte_status,
                'template_obj': None,
            }
        else:
            raise UserError(f'Provider type tidak valid: {provider_type}')
    
    def increment_usage(self):
        """Increment usage counter"""
        self.ensure_one()
        self.write({
            'usage_count': self.usage_count + 1,
            'last_used_date': fields.Datetime.now()
        })
    
    def action_sync_from_meta(self):
        """
        Sync template dari Meta WhatsApp Account
        Auto-detect template Meta berdasarkan template_name
        """
        self.ensure_one()
        
        if not self.meta_template_name:
            raise UserError('Meta template name belum di-set')
        
        # Cari template Meta
        meta_template = self.env['whatsapp.template'].search([
            ('template_name', '=', self.meta_template_name),
            ('status', '=', 'approved'),
            ('active', '=', True)
        ], limit=1)
        
        if not meta_template:
            raise UserError(
                f'Template Meta dengan nama "{self.meta_template_name}" tidak ditemukan atau belum approved.\n\n'
                f'Silakan sync template dari WhatsApp Account terlebih dahulu.'
            )
        
        self.write({
            'meta_template_id': meta_template.id,
            'meta_status': 'approved',
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Sync Berhasil',
                'message': f'Template Meta "{meta_template.name}" berhasil di-link.',
                'type': 'success',
                'sticky': False,
            }
        }

