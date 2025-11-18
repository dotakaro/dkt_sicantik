# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class SignatureWorkflow(models.Model):
    """
    Workflow untuk proses tanda tangan digital
    """
    _name = 'signature.workflow'
    _description = 'Workflow Tanda Tangan Digital'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'document_id'
    
    document_id = fields.Many2one(
        'sicantik.document',
        string='Dokumen',
        required=True,
        ondelete='cascade',
        tracking=True
    )
    document_number = fields.Char(
        related='document_id.document_number',
        string='Nomor Dokumen',
        store=True
    )
    permit_number = fields.Char(
        related='document_id.permit_number',
        string='Nomor Izin',
        store=True
    )
    
    # Workflow State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Menunggu Approval'),
        ('approved', 'Disetujui'),
        ('signing', 'Proses Tanda Tangan'),
        ('signed', 'Tertandatangani'),
        ('rejected', 'Ditolak'),
        ('cancelled', 'Dibatalkan'),
    ], string='Status', default='draft', required=True, tracking=True)
    
    # Requester
    requester_id = fields.Many2one(
        'res.users',
        string='Peminta',
        default=lambda self: self.env.user,
        required=True,
        readonly=True
    )
    request_date = fields.Datetime(
        string='Tanggal Permintaan',
        default=fields.Datetime.now,
        readonly=True
    )
    request_notes = fields.Text(
        string='Catatan Permintaan'
    )
    
    # Approver
    approver_id = fields.Many2one(
        'res.users',
        string='Penyetuju',
        tracking=True
    )
    approval_date = fields.Datetime(
        string='Tanggal Approval',
        readonly=True,
        tracking=True
    )
    approval_notes = fields.Text(
        string='Catatan Approval'
    )
    
    # Signer
    signer_id = fields.Many2one(
        'res.users',
        string='Penandatangan',
        tracking=True
    )
    signature_date = fields.Datetime(
        string='Tanggal Tanda Tangan',
        readonly=True,
        tracking=True
    )
    signature_notes = fields.Text(
        string='Catatan Tanda Tangan'
    )
    
    # Rejection
    rejection_reason = fields.Text(
        string='Alasan Penolakan'
    )
    rejected_by = fields.Many2one(
        'res.users',
        string='Ditolak Oleh',
        readonly=True
    )
    rejection_date = fields.Datetime(
        string='Tanggal Penolakan',
        readonly=True
    )
    
    # Progress Tracking
    progress = fields.Float(
        string='Progress (%)',
        compute='_compute_progress',
        store=True
    )
    
    @api.depends('state')
    def _compute_progress(self):
        """Compute workflow progress"""
        progress_map = {
            'draft': 0,
            'pending': 25,
            'approved': 50,
            'signing': 75,
            'signed': 100,
            'rejected': 0,
            'cancelled': 0,
        }
        
        for record in self:
            record.progress = progress_map.get(record.state, 0)
    
    def action_submit_for_approval(self):
        """Submit workflow untuk approval"""
        self.ensure_one()
        
        if self.state != 'draft':
            raise UserError('Hanya workflow dengan status Draft yang dapat diajukan')
        
        # Find approver (user with approval rights)
        approver = self.env['res.users'].search([
            ('groups_id', 'in', self.env.ref('base.group_system').id)
        ], limit=1)
        
        if not approver:
            raise UserError('Tidak ada user dengan hak approval')
        
        self.write({
            'state': 'pending',
            'approver_id': approver.id
        })
        
        # Create activity for approver
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            user_id=approver.id,
            summary='Approval Tanda Tangan Digital',
            note=f'Dokumen {self.document_number} memerlukan approval untuk tanda tangan digital'
        )
        
        # Send notification
        self.message_post(
            body=f'Workflow diajukan untuk approval oleh {self.requester_id.name}',
            subject='Workflow Submitted',
            message_type='notification'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Berhasil',
                'message': 'Workflow berhasil diajukan untuk approval',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_approve(self):
        """Approve workflow"""
        self.ensure_one()
        
        if self.state != 'pending':
            raise UserError('Hanya workflow dengan status Pending yang dapat disetujui')
        
        if self.env.user != self.approver_id:
            raise UserError('Anda tidak memiliki hak untuk approve workflow ini')
        
        self.write({
            'state': 'approved',
            'approval_date': fields.Datetime.now()
        })
        
        # Mark activity as done
        self.activity_ids.filtered(lambda a: a.user_id == self.env.user).action_done()
        
        # Send notification
        self.message_post(
            body=f'Workflow disetujui oleh {self.env.user.name}',
            subject='Workflow Approved',
            message_type='notification'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Berhasil',
                'message': 'Workflow berhasil disetujui',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_reject(self):
        """Reject workflow"""
        self.ensure_one()
        
        if self.state not in ['pending', 'approved']:
            raise UserError('Workflow tidak dapat ditolak pada status ini')
        
        if not self.rejection_reason:
            raise UserError('Alasan penolakan harus diisi')
        
        self.write({
            'state': 'rejected',
            'rejected_by': self.env.user.id,
            'rejection_date': fields.Datetime.now()
        })
        
        # Mark activity as done
        self.activity_ids.action_done()
        
        # Send notification
        self.message_post(
            body=f'Workflow ditolak oleh {self.env.user.name}. Alasan: {self.rejection_reason}',
            subject='Workflow Rejected',
            message_type='notification'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Ditolak',
                'message': 'Workflow telah ditolak',
                'type': 'warning',
                'sticky': False,
            }
        }
    
    def action_sign(self):
        """Execute digital signature"""
        self.ensure_one()
        
        if self.state != 'approved':
            raise UserError('Hanya workflow yang sudah disetujui yang dapat ditandatangani')
        
        # Update state to signing
        self.write({
            'state': 'signing',
            'signer_id': self.env.user.id
        })
        
        try:
            # Call document sign method
            result = self.document_id.action_sign_with_bsre()
            
            if result:
                # Update state to signed
                self.write({
                    'state': 'signed',
                    'signature_date': fields.Datetime.now()
                })
                
                # Send notification
                self.message_post(
                    body=f'Dokumen berhasil ditandatangani oleh {self.env.user.name}',
                    subject='Document Signed',
                    message_type='notification'
                )
                
                return result
            else:
                # Revert to approved state
                self.write({'state': 'approved'})
                raise UserError('Tanda tangan gagal')
                
        except Exception as e:
            # Revert to approved state
            self.write({'state': 'approved'})
            _logger.error(f'Error signing document: {str(e)}')
            raise UserError(f'Error tanda tangan: {str(e)}')
    
    def action_cancel(self):
        """Cancel workflow"""
        self.ensure_one()
        
        if self.state in ['signed', 'cancelled']:
            raise UserError('Workflow tidak dapat dibatalkan')
        
        self.write({'state': 'cancelled'})
        
        # Mark all activities as done
        self.activity_ids.action_done()
        
        # Send notification
        self.message_post(
            body=f'Workflow dibatalkan oleh {self.env.user.name}',
            subject='Workflow Cancelled',
            message_type='notification'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Dibatalkan',
                'message': 'Workflow telah dibatalkan',
                'type': 'warning',
                'sticky': False,
            }
        }
    
    def action_view_document(self):
        """View related document"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Dokumen',
            'res_model': 'sicantik.document',
            'res_id': self.document_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

