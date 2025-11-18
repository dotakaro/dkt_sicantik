# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class SicantikPermitType(models.Model):
    """
    SICANTIK Permit Type Master Data
    
    Stores permit type information synced from SICANTIK.
    """
    _name = 'sicantik.permit.type'
    _description = 'SICANTIK Permit Type'
    _rec_name = 'name'
    _order = 'name'
    
    name = fields.Char(
        string='Permit Type Name',
        required=True,
        index=True,
        help='Name of the permit type (n_perizinan)'
    )
    
    code = fields.Char(
        string='Code',
        index=True,
        help='Permit type code'
    )
    
    description = fields.Text(
        string='Description',
        help='Detailed description of this permit type'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Whether this permit type is still active'
    )
    
    # Statistics
    permit_count = fields.Integer(
        string='Permit Count',
        compute='_compute_permit_count',
        store=False,
        help='Number of permits of this type'
    )
    
    active_permit_count = fields.Integer(
        string='Active Permits',
        compute='_compute_permit_count',
        store=False,
        help='Number of active permits of this type'
    )
    
    # Sync Information
    last_sync_date = fields.Datetime(
        string='Last Sync Date',
        readonly=True,
        help='Last time this record was synced from SICANTIK'
    )
    
    _sql_constraints = [
        ('name_unique', 'unique(name)', 
         'Permit type name must be unique!')
    ]
    
    @api.depends('name')
    def _compute_permit_count(self):
        """Compute permit counts"""
        for record in self:
            permits = self.env['sicantik.permit'].search([
                ('permit_type_name', '=', record.name)
            ])
            record.permit_count = len(permits)
            record.active_permit_count = len(permits.filtered(lambda p: p.status == 'active'))
    
    def action_view_permits(self):
        """View permits of this type"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Permits: {self.name}',
            'res_model': 'sicantik.permit',
            'view_mode': 'list,form,graph,pivot',
            'domain': [('permit_type_name', '=', self.name)],
            'context': {'default_permit_type_name': self.name},
        }
    
    @api.model
    def sync_from_api(self):
        """
        Sync permit types from SICANTIK API
        
        Returns:
            dict: Sync statistics
        """
        _logger.info('Starting permit type sync...')
        
        connector = self.env['sicantik.connector'].search([('active', '=', True)], limit=1)
        if not connector:
            _logger.error('No active connector found')
            return {'synced': 0, 'skipped': 0, 'failed': 0}
        
        try:
            # Fetch permit types from API
            data = connector._make_api_request('jenisperizinanlist')
            
            if not data:
                _logger.info('No permit types to sync')
                return {'synced': 0, 'skipped': 0, 'failed': 0}
            
            synced = 0
            skipped = 0
            failed = 0
            
            for item in data:
                try:
                    name = item.get('n_perizinan')
                    if not name:
                        failed += 1
                        continue
                    
                    # Check if exists
                    existing = self.search([('name', '=', name)], limit=1)
                    
                    if existing:
                        existing.write({
                            'last_sync_date': fields.Datetime.now()
                        })
                        skipped += 1
                    else:
                        self.create({
                            'name': name,
                            'code': item.get('id'),
                            'last_sync_date': fields.Datetime.now()
                        })
                        synced += 1
                
                except Exception as e:
                    _logger.error(f'Error processing permit type: {str(e)}')
                    failed += 1
            
            _logger.info(f'Permit type sync completed: synced={synced}, skipped={skipped}, failed={failed}')
            
            return {
                'synced': synced,
                'skipped': skipped,
                'failed': failed
            }
        
        except Exception as e:
            _logger.error(f'Fatal error in permit type sync: {str(e)}')
            return {'synced': 0, 'skipped': 0, 'failed': 0}

