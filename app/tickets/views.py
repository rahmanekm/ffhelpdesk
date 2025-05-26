import os
from flask import render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from . import tickets # Reverted
from .. import db, mail
from flask_mail import Message
from ..models import Ticket, Comment, Attachment, User, TicketStatus, TicketPriority, TicketTag, Asset, AuditLog, Category, CustomField, TicketCustomField, SLAViolation
from .forms import TicketForm, CommentForm, TicketFilterForm, MergeTicketForm, CustomFieldForm, TicketUpdateForm
from datetime import datetime
from sqlalchemy import or_, and_, desc
from ..utils import save_file, allowed_file, get_client_ip


@tickets.route('/submit', methods=['GET', 'POST'])
@login_required
def submit_ticket():
    form = TicketForm()
    if form.validate_on_submit():
        ticket = Ticket(
            subject=form.subject.data,
            category=form.category.data,
            priority=form.priority.data,
            description=form.description.data,
            submitter=current_user
        )
        db.session.add(ticket)

        # Handle file attachment
        if form.attachment.data:
            file = form.attachment.data
            filename = secure_filename(file.filename)
            file_path = os.path.join(
                current_app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            attachment = Attachment(
                filename=filename,
                file_path=file_path,
                file_type=file.content_type,
                file_size=os.path.getsize(file_path),
                ticket=ticket
            )
            db.session.add(attachment)

        db.session.commit()

        # Send notification email
        msg = Message('New Support Ticket Submitted',
                      sender=current_app.config['MAIL_DEFAULT_SENDER'],
                      recipients=[current_user.email])
        msg.body = f'''
        Your ticket has been submitted successfully.
        Ticket ID: {ticket.id}
        Subject: {ticket.subject}
        Category: {ticket.category}
        Priority: {ticket.priority}

        You can view your ticket at: {url_for('tickets.view_ticket', ticket_id=ticket.id, _external=True)}
        '''
        mail.send(msg)

        flash('Your ticket has been submitted successfully!')
        return redirect(url_for('tickets.view_ticket', ticket_id=ticket.id))
    return render_template('tickets/submit.html', form=form)


@tickets.route('/')
@login_required
def list_tickets():
    page = request.args.get('page', 1, type=int)
    tickets_query = Ticket.query.filter(
        (Ticket.submitter_id == current_user.id) |
        (Ticket.assigned_agent_id == current_user.id)
    ).order_by(desc(Ticket.created_at))

    pagination = tickets_query.paginate(
        page=page, per_page=current_app.config['TICKETS_PER_PAGE'],
        error_out=False)
    tickets_list = pagination.items

    return render_template('tickets/list.html',
                           tickets=tickets_list,
                           pagination=pagination)


@tickets.route('/create', methods=['GET', 'POST'])
@login_required
def create_ticket():
    if request.method == 'POST':
        subject = request.form.get('subject')
        description = request.form.get('description')
        category_id = request.form.get('category_id')
        priority_id = request.form.get('priority_id')

        ticket = Ticket(
            subject=subject,
            description=description,
            category_id=category_id,
            priority_id=priority_id,
            status_id=TicketStatus.query.filter_by(name='Open').first().id,
            submitter_id=current_user.id,
            requester_id=current_user.id
        )

        db.session.add(ticket)
        db.session.commit()

        flash('Ticket created successfully!', 'success')
        return redirect(url_for('tickets.view_ticket', ticket_id=ticket.id))

    categories = Category.query.all()
    priorities = TicketPriority.query.all()
    return render_template('tickets/create.html',
                           categories=categories,
                           priorities=priorities)


@tickets.route('/<int:ticket_id>')
@login_required
def view_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    if not (ticket.submitter_id == current_user.id or
            ticket.assigned_agent_id == current_user.id or
            current_user.role in ['admin', 'agent']):
        flash('You do not have permission to view this ticket.', 'danger')
        return redirect(url_for('main.dashboard'))

    comment_form = CommentForm()
    merge_form = MergeTicketForm(exclude_id=ticket_id)
    update_form = TicketUpdateForm()

    # Get related tickets based on similar subject or category
    related_tickets = Ticket.query.filter(
        and_(
            Ticket.id != ticket.id,
            or_(
                Ticket.category_id == ticket.category_id,
                Ticket.subject.ilike(f"%{ticket.subject}%")
            )
        )
    ).limit(5).all()

    # Get all users for assignment
    users = User.query.all()
    statuses = TicketStatus.query.all()
    priorities = TicketPriority.query.all()

    return render_template('tickets/view.html',
                           ticket=ticket,
                           comment_form=comment_form,
                           merge_form=merge_form,
                           form=update_form,
                           related_tickets=related_tickets,
                           users=users,
                           statuses=statuses,
                           priorities=priorities)


@tickets.route('/<int:ticket_id>/update', methods=['POST'])
@login_required
def update_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    form = TicketUpdateForm()

    if form.validate_on_submit():
        # Store old values for audit logging
        old_values = {
            'status_id': ticket.status_id,
            'priority_id': ticket.priority_id,
            'assigned_agent_id': ticket.assigned_agent_id
        }

        # Update ticket values
        ticket.status_id = form.status.data
        ticket.priority_id = form.priority.data
        ticket.assigned_agent_id = form.assigned_to.data if form.assigned_to.data != 0 else None

        # Update closed_at field if status is changed to a closed status
        new_status = TicketStatus.query.get(form.status.data)
        if new_status and new_status.is_closed is not ticket.closed_at:
            ticket.closed_at = datetime.utcnow()
        elif new_status and not new_status.is_closed:
            ticket.closed_at = None

        # Create audit log for changes
        changes = {}
        for field, old_value in old_values.items():
            new_value = getattr(ticket, field)
            if old_value != new_value:
                changes[field] = {
                    'old': old_value,
                    'new': new_value,
                    'old_name': get_old_name(field, old_value),
                    'new_name': get_new_name(field, new_value)
                }

        if changes:
            log = AuditLog(
                action='update',
                entity_type='ticket',
                entity_id=ticket.id,
                user_id=current_user.id,
                changes=changes,
                ip_address=get_client_ip()
            )
            db.session.add(log)

        db.session.commit()
        flash('Ticket updated successfully.', 'success')

    return redirect(url_for('.view_ticket', ticket_id=ticket.id))


def get_old_name(field, value):
    if field == 'status_id':
        status = TicketStatus.query.get(value)
        return status.name if status else 'Unknown'
    elif field == 'priority_id':
        priority = TicketPriority.query.get(value)
        return priority.name if priority else 'Unknown'
    elif field == 'assigned_agent_id':
        user = User.query.get(value)
        return user.username if user else 'Unassigned'
    return str(value)


def get_new_name(field, value):
    if field == 'status_id':
        status = TicketStatus.query.get(value)
        return status.name if status else 'Unknown'
    elif field == 'priority_id':
        priority = TicketPriority.query.get(value)
        return priority.name if priority else 'Unknown'
    elif field == 'assigned_agent_id':
        user = User.query.get(value)
        return user.username if user else 'Unassigned'
    return str(value)


@tickets.route('/<int:ticket_id>/merge', methods=['POST'])
@login_required
def merge_tickets(ticket_id):
    source_ticket = Ticket.query.get_or_404(ticket_id)
    form = MergeTicketForm(exclude_id=ticket_id)

    if form.validate_on_submit():
        target_ticket = Ticket.query.get_or_404(form.target_ticket.data)

        if source_ticket.merge_with(target_ticket):
            # Move all comments to target ticket
            Comment.query.filter_by(ticket_id=source_ticket.id).update(
                {'ticket_id': target_ticket.id})

            # Move all attachments to target ticket
            Attachment.query.filter_by(ticket_id=source_ticket.id).update({
                'ticket_id': target_ticket.id})

            # Create audit logs
            log = AuditLog(
                action='merge',
                entity_type='ticket',
                entity_id=source_ticket.id,
                user_id=current_user.id,
                changes={'merged_into': target_ticket.id},
                ip_address=get_client_ip()
            )
            db.session.add(log)

            db.session.commit()
            flash(
                f'Ticket #{source_ticket.id} has been merged into ticket #{target_ticket.id}.'
            )
            return redirect(
                url_for(
                    '.view_ticket',
                    ticket_id=target_ticket.id))
        else:
            flash('Unable to merge tickets. Please try again.')

    return redirect(url_for('.view_ticket', ticket_id=ticket_id))


@tickets.route('/<int:ticket_id>/comment', methods=['POST'])
@login_required
def add_comment(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    form = CommentForm()

    if form.validate_on_submit():
        comment = Comment(
            content=form.content.data,
            is_internal=form.is_internal.data == '1',
            ticket_id=ticket.id,
            author_id=current_user.id
        )
        db.session.add(comment)

        # Handle attachments
        if 'attachments' in request.files:
            for file in request.files.getlist('attachments'):
                if file and allowed_file(file.filename):
                    filename = save_file(file)
                    attachment = Attachment(
                        filename=file.filename,
                        file_path=filename,
                        file_type=file.content_type,
                        file_size=os.path.getsize(filename),
                        ticket_id=ticket.id,
                        comment_id=comment.id
                    )
                    db.session.add(attachment)

        # Update ticket's first response time if this is the first public
        # comment
        if not ticket.first_response_at and not form.is_internal.data == '1':
            ticket.first_response_at = datetime.utcnow()

        # Create audit log for the comment
        log = AuditLog(
            action='comment',
            entity_type='ticket',
            entity_id=ticket.id,
            user_id=current_user.id,
            changes={
                'comment_id': comment.id,
                'is_internal': comment.is_internal},
            ip_address=get_client_ip())
        db.session.add(log)

        db.session.commit()
        flash('Comment added successfully.', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}', 'danger')

    return redirect(url_for('.view_ticket', ticket_id=ticket.id))


@tickets.route('/api/search')
@login_required
def search_tickets():
    query = request.args.get('q', '')
    if not query:
        return jsonify([])

    tickets = Ticket.query.filter(
        or_(
            Ticket.subject.ilike(f"%{query}%"),
            Ticket.id.in_([id.strip() for id in query.split(',') if id.strip().isdigit()])
        )
    ).limit(10).all()

    return jsonify([{
        'id': ticket.id,
        'subject': ticket.subject,
        'status': ticket.get_status(),
        'priority': ticket.get_priority()
    } for ticket in tickets])


@tickets.route('/dashboard')
@login_required
def dashboard():
    # Get statistics for tickets
    total_tickets = Ticket.query.count()
    open_tickets = Ticket.query.join(TicketStatus).filter(
        TicketStatus.is_closed is not True).count()
    my_tickets = Ticket.query.filter_by(
        assigned_agent_id=current_user.id).count()
    overdue_tickets = Ticket.query.filter(
        Ticket.due_date < datetime.utcnow()).count()

    # Get recent activity
    recent_tickets = Ticket.query.order_by(
        Ticket.created_at.desc()).limit(5).all()
    recent_comments = Comment.query.order_by(
        Comment.created_at.desc()).limit(5).all()

    # Get ticket statistics by category
    categories = Category.query.all()
    category_stats = []
    for category in categories:
        stats = {
            'name': category.name,
            'total': Ticket.query.filter_by(category_id=category.id).count(),
            'open': Ticket.query.join(TicketStatus).filter(
                and_(
                    Ticket.category_id == category.id,
        TicketStatus.is_closed is not True
                )
            ).count()
        }
        category_stats.append(stats)

    return render_template('tickets/dashboard.html',
                           total_tickets=total_tickets,
                           open_tickets=open_tickets,
                           my_tickets=my_tickets,
                           overdue_tickets=overdue_tickets,
                           recent_tickets=recent_tickets,
                           recent_comments=recent_comments,
                           category_stats=category_stats)


@tickets.route('/my')
@login_required
def my_tickets():
    page = request.args.get('page', 1, type=int)
    tickets_query = Ticket.query.filter_by(
        submitter_id=current_user.id).order_by(
        desc(
            Ticket.created_at))

    pagination = tickets_query.paginate(
        page=page, per_page=current_app.config['TICKETS_PER_PAGE'],
        error_out=False)
    tickets_list = pagination.items

    return render_template('tickets/list.html',
                           tickets=tickets_list,
                           pagination=pagination,
                           title='My Tickets')


@tickets.route('/assigned')
@login_required
def assigned_tickets():
    if current_user.role not in ['admin', 'agent']:
        flash('You do not have permission to view assigned tickets.', 'danger')
        return redirect(url_for('main.dashboard'))

    page = request.args.get('page', 1, type=int)
    tickets_query = Ticket.query.filter_by(
        assigned_agent_id=current_user.id).order_by(
        desc(
            Ticket.created_at))

    pagination = tickets_query.paginate(
        page=page, per_page=current_app.config['TICKETS_PER_PAGE'],
        error_out=False)
    tickets_list = pagination.items

    return render_template('tickets/list.html',
                           tickets=tickets_list,
                           pagination=pagination,
                           title='Assigned Tickets')


@tickets.route('/<int:ticket_id>/delete', methods=['POST'])
@login_required
def delete_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)

    # Check if user has permission to delete
    if not (current_user.role in ['admin', 'agent']
            or ticket.submitter_id == current_user.id):
        flash('You do not have permission to delete this ticket.', 'danger')
        return redirect(url_for('main.dashboard'))

    try:
        # Delete related records first
        # Delete comments
        Comment.query.filter_by(ticket_id=ticket.id).delete()

        # Delete attachments
        Attachment.query.filter_by(ticket_id=ticket.id).delete()

        # Delete custom fields
        TicketCustomField.query.filter_by(ticket_id=ticket.id).delete()

        # Delete SLA violations
        SLAViolation.query.filter_by(ticket_id=ticket.id).delete()

        # Delete audit logs
        AuditLog.query.filter_by(
            entity_type='ticket',
            entity_id=ticket.id).delete()

        # Create audit log for the deletion
        log = AuditLog(
            action='delete',
            entity_type='ticket',
            entity_id=ticket.id,
            user_id=current_user.id,
            changes={'ticket_id': ticket.id, 'subject': ticket.subject},
            ip_address=get_client_ip()
        )
        db.session.add(log)

        # Finally delete the ticket
        db.session.delete(ticket)
        db.session.commit()

        flash('Ticket has been deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while deleting the ticket.', 'danger')
        current_app.logger.error(
            f'Error deleting ticket {ticket_id}: {
                str(e)}')

    return redirect(url_for('main.dashboard'))
