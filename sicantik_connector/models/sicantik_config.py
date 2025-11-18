# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
import requests
import logging
import xml.etree.ElementTree as ET

_logger = logging.getLogger(__name__)


class SicantikConfig(models.Model):
    """
    SICANTIK API Configuration
    
    Stores API connection settings and credentials for SICANTIK integration.
    Only one active configuration is allowed at a time.
    """
    _name = 'sicantik.config'
    _description = 'SICANTIK API Configuration'
    _rec_name = 'name'
    
    # Basic Info
    name = fields.Char(
        string='Configuration Name',
        required=True,
        default='SICANTIK Production',
        help='Descriptive name for this configuration'
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Only one configuration can be active at a time'
    )
    
    # API Settings
    api_url = fields.Char(
        string='API Base URL',
        required=True,
        default='https://perizinan.karokab.go.id/backoffice/api',
        help='Base URL for SICANTIK API endpoints'
    )
    api_timeout = fields.Integer(
        string='API Timeout (seconds)',
        default=30,
        help='Maximum time to wait for API response'
    )
    
    # Sync Settings
    sync_interval = fields.Integer(
        string='Sync Interval (minutes)',
        default=15,
        help='How often to sync data from SICANTIK'
    )
    sync_limit = fields.Integer(
        string='Sync Limit (records per batch)',
        default=100,
        help='Number of records to fetch per API call'
    )
    
    # Rate Limiting
    rate_limit_enabled = fields.Boolean(
        string='Enable Rate Limiting',
        default=True,
        help='Prevent overwhelming the SICANTIK server'
    )
    rate_limit_requests = fields.Integer(
        string='Max Requests per Second',
        default=10,
        help='Maximum number of API requests per second'
    )
    
    # Statistics (readonly)
    last_sync_date = fields.Datetime(
        string='Last Sync Date',
        readonly=True,
        help='Last time data was synced from SICANTIK'
    )
    total_permits_synced = fields.Integer(
        string='Total Permits Synced',
        readonly=True,
        help='Total number of permits synced since installation'
    )
    last_sync_duration = fields.Float(
        string='Last Sync Duration (seconds)',
        readonly=True,
        help='Duration of the last sync operation'
    )
    
    # Status
    connection_status = fields.Selection([
        ('unknown', 'Unknown'),
        ('connected', 'Connected'),
        ('error', 'Connection Error')
    ], string='Connection Status', default='unknown', readonly=True)
    
    last_error = fields.Text(
        string='Last Error',
        readonly=True,
        help='Details of the last connection error'
    )
    
    @api.constrains('active')
    def _check_single_active(self):
        """Ensure only one configuration is active"""
        if self.active:
            other_active = self.search([
                ('active', '=', True),
                ('id', '!=', self.id)
            ])
            if other_active:
                raise ValidationError(
                    'Only one SICANTIK configuration can be active at a time. '
                    f'Please deactivate "{other_active[0].name}" first.'
                )
    
    @api.constrains('api_url')
    def _check_api_url(self):
        """Validate API URL format"""
        for record in self:
            if not record.api_url:
                continue
            
            if not record.api_url.startswith(('http://', 'https://')):
                raise ValidationError(
                    'API URL must start with http:// or https://'
                )
            
            if record.api_url.endswith('/'):
                record.api_url = record.api_url.rstrip('/')
    
    @api.constrains('sync_interval', 'sync_limit', 'rate_limit_requests')
    def _check_positive_values(self):
        """Ensure positive values for numeric fields"""
        for record in self:
            if record.sync_interval <= 0:
                raise ValidationError('Sync interval must be greater than 0')
            if record.sync_limit <= 0:
                raise ValidationError('Sync limit must be greater than 0')
            if record.rate_limit_requests <= 0:
                raise ValidationError('Rate limit must be greater than 0')
    
    def action_test_connection(self):
        """
        Test connection to SICANTIK API
        
        Tries to fetch permit count to verify API accessibility
        """
        self.ensure_one()
        
        try:
            url = f'{self.api_url}/jumlahPerizinan'
            _logger.info(f'Testing connection to: {url}')
            
            response = requests.get(url, timeout=self.api_timeout)
            _logger.info(f'Response status: {response.status_code}')
            _logger.info(f'Response headers: {response.headers}')
            _logger.info(f'Response content (first 200 chars): {response.text[:200]}')
            
            response.raise_for_status()
            
            # Check if response is empty
            if not response.text or response.text.strip() == '':
                raise ValueError('API mengembalikan response kosong')
            
            # Check content type and parse accordingly
            content_type = response.headers.get('Content-Type', '')
            _logger.info(f'Content-Type: {content_type}')
            
            if 'xml' in content_type.lower() or response.text.strip().startswith('<?xml'):
                # Parse XML response
                try:
                    root = ET.fromstring(response.text)
                    # Extract jumlahPerizinan from XML
                    jumlah_elem = root.find('.//jumlahPerizinan')
                    if jumlah_elem is not None:
                        jumlah = jumlah_elem.text
                        data = {'total': jumlah}
                        _logger.info(f'XML parsed successfully: {data}')
                    else:
                        raise ValueError('Element jumlahPerizinan tidak ditemukan dalam XML')
                except ET.ParseError as xml_err:
                    _logger.error(f'XML parsing error: {xml_err}. Response: {response.text[:500]}')
                    raise ValueError(f'API tidak mengembalikan XML valid: {str(xml_err)}')
            else:
                # Try to parse JSON
                try:
                    data = response.json()
                    _logger.info(f'JSON parsed successfully: {data}')
                except ValueError as json_err:
                    _logger.error(f'JSON parsing error. Response: {response.text[:500]}')
                    raise ValueError(f'API tidak mengembalikan JSON valid. Response: {response.text[:100]}')
            
            self.write({
                'connection_status': 'connected',
                'last_error': False
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Koneksi Berhasil',
                    'message': f'Berhasil terhubung ke API SICANTIK. Ditemukan {data.get("total", "N/A")} jenis izin.',
                    'type': 'success',
                    'sticky': False,
                }
            }
        
        except requests.exceptions.Timeout:
            error_msg = f'Connection timeout after {self.api_timeout} seconds'
            _logger.error(error_msg)
            self.write({
                'connection_status': 'error',
                'last_error': error_msg
            })
            raise ValidationError(error_msg)
        
        except requests.exceptions.RequestException as e:
            error_msg = f'Connection error: {str(e)}'
            _logger.error(error_msg)
            self.write({
                'connection_status': 'error',
                'last_error': error_msg
            })
            raise ValidationError(error_msg)
        
        except Exception as e:
            error_msg = f'Unexpected error: {str(e)}'
            _logger.error(error_msg)
            self.write({
                'connection_status': 'error',
                'last_error': error_msg
            })
            raise ValidationError(error_msg)
    
    def action_open_dashboard(self):
        """Open SICANTIK dashboard"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'SICANTIK Dashboard',
            'res_model': 'sicantik.permit',
            'view_mode': 'kanban,list,form,graph,pivot',
            'context': {'search_default_active': 1},
            'domain': [],
        }
    
    def action_sync_now(self):
        """Manually trigger data sync"""
        self.ensure_one()
        
        connector = self.env['sicantik.connector'].search([], limit=1)
        if not connector:
            connector = self.env['sicantik.connector'].create({
                'name': 'Default Connector',
                'config_id': self.id
            })
        
        return connector.action_sync_permits()
    
    def get_api_url(self, endpoint):
        """
        Get full API URL for an endpoint
        
        Args:
            endpoint (str): API endpoint path
        
        Returns:
            str: Full URL
        """
        self.ensure_one()
        endpoint = endpoint.lstrip('/')
        return f'{self.api_url}/{endpoint}'

