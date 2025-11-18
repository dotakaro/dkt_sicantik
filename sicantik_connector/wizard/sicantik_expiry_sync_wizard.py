# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class SicantikExpirySyncWizard(models.TransientModel):
    """
    Wizard for syncing expiry dates from SICANTIK API
    
    Provides user-friendly interface for manual expiry sync with:
    - Permit count without expiry
    - Estimated duration
    - Warning about workaround solution
    """
    _name = 'sicantik.expiry.sync.wizard'
    _description = 'SICANTIK Expiry Sync Wizard'
    
    connector_id = fields.Many2one(
        'sicantik.connector',
        string='Connector',
        required=True,
        default=lambda self: self.env['sicantik.connector'].search([('active', '=', True)], limit=1)
    )
    
    permits_without_expiry = fields.Integer(
        string='Permits Without Expiry',
        compute='_compute_permits_count',
        help='Number of active permits without expiry date'
    )
    
    estimated_duration = fields.Char(
        string='Estimated Duration',
        compute='_compute_estimated_duration',
        help='Estimated time to complete sync'
    )
    
    max_permits = fields.Integer(
        string='Max Permits to Sync',
        help='Leave empty to sync all permits'
    )
    
    @api.depends('connector_id')
    def _compute_permits_count(self):
        """Compute number of permits without expiry"""
        for wizard in self:
            wizard.permits_without_expiry = self.env['sicantik.permit'].search_count([
                ('expiry_date', '=', False),
                ('status', '=', 'active'),
                ('permit_number', '!=', False)
            ])
    
    @api.depends('permits_without_expiry', 'max_permits')
    def _compute_estimated_duration(self):
        """Compute estimated duration"""
        for wizard in self:
            # Determine actual count to sync
            count = wizard.max_permits if wizard.max_permits else wizard.permits_without_expiry
            
            # Estimate: ~0.15 seconds per permit
            seconds = count * 0.15
            
            if seconds < 60:
                wizard.estimated_duration = f'{int(seconds)} seconds'
            elif seconds < 3600:
                minutes = seconds / 60
                wizard.estimated_duration = f'{int(minutes)} minutes'
            else:
                hours = seconds / 3600
                wizard.estimated_duration = f'{hours:.1f} hours'
    
    def action_sync(self):
        """Execute the sync"""
        self.ensure_one()
        
        if self.permits_without_expiry == 0:
            raise UserError('No permits to sync')
        
        if not self.connector_id:
            raise UserError('No active connector found')
        
        # Start sync
        result = self.connector_id.sync_expiry_dates_workaround(
            max_permits=self.max_permits if self.max_permits else None
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Expiry Sync Completed',
                'message': f'Synced: {result["synced"]}, Failed: {result["failed"]}, Duration: {result["duration"]:.2f}s',
                'type': 'success' if result['synced'] > 0 else 'warning',
                'sticky': True,
            }
        }
    
    def action_test_sync(self):
        """Test sync with 10 permits"""
        self.ensure_one()
        
        result = self.connector_id.sync_expiry_dates_workaround(max_permits=10)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Test Sync Completed',
                'message': f'Synced: {result["synced"]}, Failed: {result["failed"]}, Duration: {result["duration"]:.2f}s',
                'type': 'success' if result['synced'] > 0 else 'warning',
                'sticky': False,
            }
        }

