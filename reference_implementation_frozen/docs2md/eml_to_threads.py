#!/usr/bin/env python3
"""
Library to convert .eml files into organized Markdown conversation threads.

VERSION: 3.5.0
🤖 AI AGENTS: INCREMENT VERSION NUMBER WHEN MODIFYING THIS FILE!
   - Major changes (breaking): X.0.0
   - New features: X.Y.0
   - Bug fixes/improvements: X.Y.Z

v3.5.0: Enhanced HTML to plain text conversion using existing html2text library.
        Now properly extracts HTML email bodies and converts them to readable plain text.
        DESIGN DECISION: Inline images (Content-ID) are INTENTIONALLY IGNORED.
        This system processes emails gracefully but does NOT extract inline images.
v3.0.0: Refactored to use the the 'mail-parser' library for robust, resilient parsing
        and graceful degradation. This approach handles corrupted and malformed
        emails by extracting as much information as possible and logging
        specific defects, rather than failing completely.
"""

import os
import re
import base64
import hashlib
import logging
import threading
import traceback
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any

# Use the robust mail-parser library for all email parsing.
# It gracefully handles malformed emails and provides defect reports.
# Project URL: https://github.com/SpamScope/mail-parser
import mailparser

# Script version - AI agents must increment when modifying!
EML_CONVERTER_VERSION = "3.5.0"

# Set up thread-safe logger for library use
logger = logging.getLogger(__name__)

def log_with_thread_info(level: str, message: str) -> None:
    """Log message with thread information for bulletproof logging."""
    thread_id = threading.current_thread().ident or 0
    thread_name = threading.current_thread().name
    log_msg = f"[{thread_name}:{thread_id}] {message}"
    getattr(logger, level.lower())(log_msg)

class EmailMessage:
    """
    Represents a single email message, acting as a wrapper around the object
    returned by the 'mail-parser' library to provide a consistent interface.
    """
    def __init__(self, parsed_mail: mailparser.MailParser, eml_file_path: Path):
        self.mail = parsed_mail
        self.source_path = eml_file_path.parent
        self.source_filename = eml_file_path.name  # Store original filename for traceability
        
        # Core properties are now accessed directly from the parsed object.
        self.message_id = self.mail.message_id or f"<generated-{eml_file_path.stem}>"
        self.subject = self._clean_subject(self.mail.subject or '')
        self.from_addr = self._format_address(self.mail.from_)
        self.to_addr = self._format_address(self.mail.to)
        self.date = self._normalize_date(self.mail.date)
        self.references = self.mail.references
        self.in_reply_to = self.mail.in_reply_to
        self.content = self._extract_email_body()
        self.attachments = self._extract_attachments()

    def _format_address(self, addresses: List[Tuple[str, str]]) -> str:
        """Formats a list of address tuples into a single, readable string."""
        if not addresses:
            return "Unknown"
        
        formatted_addrs = []
        for name, addr in addresses:
            if name:
                formatted_addrs.append(f"{name} <{addr}>")
            else:
                formatted_addrs.append(addr)
        return ', '.join(formatted_addrs)

    def _normalize_date(self, date_obj: Optional[datetime]) -> datetime:
        """
        Ensure all datetime objects are offset-aware and in UTC to allow for safe comparison.
        See: https://docs.python.org/3/library/datetime.html#aware-and-naive-objects
        """
        if not date_obj:
            return datetime.now(timezone.utc)
        
        if date_obj.tzinfo is None or date_obj.tzinfo.utcoffset(date_obj) is None:
            # It's naive, so assume UTC and make it aware.
            return date_obj.replace(tzinfo=timezone.utc)
        else:
            # It's aware, so convert it to UTC.
            return date_obj.astimezone(timezone.utc)

    def _clean_subject(self, subject: str) -> str:
        """Clean subject line by removing Re:, Fwd: prefixes."""
        if not subject:
            return "No Subject"
        cleaned = re.sub(r'^(Re|Fwd?|Fw):\s*', '', subject, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned or "No Subject"

    def _extract_email_body(self) -> str:
        """Extract email body, preferring plain text, converting HTML only when necessary."""
        
        # 1. BEST CASE: Plain text exists - use it directly
        if self.mail.text_plain:
            return '\n'.join(self.mail.text_plain)
        
        # 2. FALLBACK CASE: Only HTML exists - convert to plain text
        elif self.mail.text_html:
            try:
                import html2text
                h = html2text.HTML2Text()
                h.ignore_links = False
                h.body_width = 0  # Don't wrap lines
                
                html_content = '\n'.join(self.mail.text_html)
                converted = h.handle(html_content)
                return converted
            except Exception as e:
                log_with_thread_info('warning', f"HTML conversion failed for {self.source_filename}: {e}. Using raw HTML.")
                return '\n'.join(self.mail.text_html)
        
        # 3. LAST RESORT: Generic body (might be HTML, might be plain text)
        elif self.mail.body:
            # Check if it looks like HTML
            if self._is_html_content(self.mail.body):
                try:
                    import html2text
                    h = html2text.HTML2Text()
                    h.ignore_links = False
                    h.body_width = 0
                    converted = h.handle(self.mail.body)
                    return converted
                except Exception as e:
                    log_with_thread_info('warning', f"Generic HTML conversion failed for {self.source_filename}: {e}. Using raw content.")
                    return self.mail.body
            else:
                return self.mail.body
        
        return "No message body found."

    def _is_html_content(self, content: str) -> bool:
        """Simple check if content contains HTML tags."""
        import re
        # Look for HTML tags
        html_pattern = r'<[^>]+>'
        return bool(re.search(html_pattern, content))

    def _extract_attachments(self) -> List[Tuple[str, bytes, str]]:
        """
        Extracts both standard and inline attachments from email messages.

        This method now handles two types of attachments:
        1.  Standard file attachments (e.g., PDFs, Word docs).
        2.  Inline images referenced by a Content-ID (CID) in the HTML body.

        It sanitizes filenames to remove invalid characters, which is crucial
        for inline attachments where the filename might be derived from a
        Content-ID like "<image123>".
        """
        attachments = []
        
        for att in self.mail.attachments:
            filename = att.get('filename')
            payload = att.get('payload', '')
            content_type = att.get('mail_content_type', 'application/octet-stream')
            content_id = att.get('content_id')

            # If filename is missing, try to generate one from Content-ID
            if not filename and content_id:
                # Sanitize Content-ID to be a valid filename
                # e.g., "<red_pixel>" -> "red_pixel"
                sanitized_cid = re.sub(r'[<>:"/\\|?*]', '', content_id)
                
                # Attempt to guess extension from MIME type
                import mimetypes
                extension = mimetypes.guess_extension(content_type) or '.bin'
                filename = f"{sanitized_cid}{extension}"

            if not filename:
                # Fallback for attachments with no filename or Content-ID
                import mimetypes
                extension = mimetypes.guess_extension(content_type) or '.bin'
                # Create a unique but deterministic name
                payload_hash = hashlib.sha1(payload.encode('utf-8', errors='replace') if isinstance(payload, str) else payload).hexdigest()[:8]
                filename = f"attachment_{payload_hash}{extension}"
                log_with_thread_info('warning', f"Attachment has no filename or Content-ID. Generated filename: {filename}")

            # Sanitize the final filename regardless of its origin
            filename = re.sub(r'[<>:"/\\|?*]', '', filename)

            if not payload:
                log_with_thread_info('warning', f"Skipping attachment '{filename}' due to empty payload.")
                continue

            decoded_payload = b''
            try:
                if isinstance(payload, str):
                    decoded_payload = base64.b64decode(payload.encode('ascii'))
                elif isinstance(payload, bytes):
                    decoded_payload = base64.b64decode(payload)
            except (ValueError, TypeError) as e:
                log_with_thread_info('warning', f"Could not decode attachment '{filename}': {e}. Using raw payload.")
                decoded_payload = payload.encode('utf-8', errors='replace') if isinstance(payload, str) else payload

            attachments.append((filename, decoded_payload, content_type))
            
        return attachments

    def remove_quoted_text(self) -> str:
        """Remove quoted text from email content."""
        # mail-parser does a good job of this, but we can add more cleaning if needed.
        return self.content

class EmailThread:
    """Represents a conversation thread containing multiple emails."""
    def __init__(self, subject: str):
        self.subject = subject
        self.emails: List[EmailMessage] = []
        self.source_filenames: List[str] = []  # Track original EML filenames

    def add_email(self, email_msg: EmailMessage):
        """Add an email to this thread."""
        self.emails.append(email_msg)
        self.emails.sort(key=lambda x: x.date, reverse=True)
        # Track source filenames for traceability
        if email_msg.source_filename not in self.source_filenames:
            self.source_filenames.append(email_msg.source_filename)

    def get_thread_filename(self) -> str:
        """Generate a safe filename for this thread with source file traceability."""
        # If thread contains only one email, use its original filename
        if len(self.emails) == 1 and len(self.source_filenames) == 1:
            original_filename = self.source_filenames[0]
            # Remove .eml extension and add .thread.md
            base_name = original_filename[:-4] if original_filename.endswith('.eml') else original_filename
            return f"{base_name}.thread.md"
        
        # For multi-email threads, use subject-based naming with source file info
        safe_subject = re.sub(r'[^\w\s-]', '', self.subject).strip()
        safe_subject = re.sub(r'[-\s]+', '_', safe_subject).lower()[:60] or "untitled"  # Shortened for space
        
        # Add source file indicator for multi-email threads
        source_indicator = f"_from_{len(self.source_filenames)}_files"
        
        if self.emails:
            oldest_email = min(self.emails, key=lambda x: x.date)
            date_str = oldest_email.date.strftime("%Y%m%d")
            return f"{date_str}_{safe_subject}{source_indicator}.thread.md"
        
        return f"{safe_subject}{source_indicator}.thread.md"

class AttachmentManager:
    """Manages extraction and deduplication of email attachments."""
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.attachment_hashes: Dict[str, str] = {}

    def save_attachment(self, filename: str, content: Any) -> str:
        """Save attachment and return the final filename used."""
        if not content:
            log_with_thread_info('warning', f"Skipping zero-byte attachment: {filename}")
            return filename

        # Ensure content is bytes before hashing
        if isinstance(content, str):
            content_bytes = content.encode('utf-8')
        else:
            content_bytes = content

        # Use SHA256 to create a unique hash for deduplication.
        # See: https://docs.python.org/3/library/hashlib.html#hashlib.sha256
        content_hash = hashlib.sha256(content_bytes).hexdigest()
        if content_hash in self.attachment_hashes:
            return self.attachment_hashes[content_hash]

        file_path = self.output_dir / filename
        counter = 1
        base, ext = os.path.splitext(filename)
        while file_path.exists():
            file_path = self.output_dir / f"{base}_{counter}{ext}"
            counter += 1

        try:
            file_path.write_bytes(content_bytes)
            final_filename = file_path.name
            self.attachment_hashes[content_hash] = final_filename
            return final_filename
        except Exception as e:
            log_with_thread_info('error', f"Failed to save attachment {filename}: {e}")
            return filename

class EmlToThreadsConverter:
    """Orchestrates the conversion of .eml files to Markdown threads."""
    def __init__(self, input_path: Path, output_path: Path):
        self.input_path = input_path
        self.output_path = output_path
        self.threads_by_path: Dict[Path, Dict[str, EmailThread]] = {}
        self.failures: List[Dict[str, Any]] = []

    def convert(self) -> Dict[str, Any]:
        """Main conversion function. Returns a dictionary with conversion statistics."""
        log_with_thread_info('info', f"📬 Starting EML conversion v{EML_CONVERTER_VERSION} from {self.input_path} to {self.output_path}")
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        emails, total_eml_files = self._parse_eml_directory()
        
        if not emails:
            log_with_thread_info('warning', "No .eml files could be successfully parsed.")
            return {"total_files": total_eml_files, "successful_files": 0, "failed_files": len(self.failures), "threads_created": 0, "failures": self.failures}
        
        log_with_thread_info('info', f"Successfully parsed {len(emails)} of {total_eml_files} .eml files with graceful degradation.")
        self._build_threads(emails)
        
        thread_count = sum(len(threads) for threads in self.threads_by_path.values())
        log_with_thread_info('info', f"Organized emails into {thread_count} conversation threads.")
        
        self._generate_output()
        log_with_thread_info('info', f"Conversion complete for directory. Output is in {self.output_path}")

        return {"total_files": total_eml_files, "successful_files": len(emails), "failed_files": len(self.failures), "threads_created": thread_count, "failures": self.failures}

    def _parse_eml_directory(self) -> Tuple[List[EmailMessage], int]:
        """
        Parse all .eml files in a directory, using mail-parser for resilience
        and logging any defects found for graceful degradation.
        """
        emails = []
        eml_files = sorted(self.input_path.rglob('*.eml'))
        total_files = len(eml_files)

        for eml_file in eml_files:
            try:
                # Use mail-parser, which is designed to be resilient.
                # See: https://github.com/SpamScope/mail-parser#usage
                parsed_mail = mailparser.parse_from_file(str(eml_file))
                
                # GRACEFUL DEGRADATION: Check for and log any parsing defects.
                if parsed_mail.defects:
                    log_with_thread_info('warning', f"🟡 File '{eml_file.name}' has defects, but was partially parsed:")
                    for defect in parsed_mail.defects:
                        defect_name = defect.get('name', 'Unknown Defect')
                        defect_details = defect.get('details', 'No details')
                        log_with_thread_info('warning', f"  - Defect: {defect_name} ({defect_details})")
                
                # Even with defects, we create an EmailMessage to extract what we can.
                email_msg = EmailMessage(parsed_mail, eml_file)
                emails.append(email_msg)

            except Exception as e:
                # This will now only catch catastrophic failures where mail-parser itself fails.
                log_with_thread_info('error', f"🔴 Catastrophic failure on file '{eml_file.name}': {e}")
                log_with_thread_info('error', traceback.format_exc())
                self.failures.append({"file": str(eml_file.relative_to(self.input_path.parent)), "error": str(e), "exception": type(e).__name__, "traceback": traceback.format_exc()})
                
                # Create an error markdown file for this specific failure
                error_filename = f"{eml_file.stem}_conversion_error.md"
                error_filepath = self.output_path / eml_file.relative_to(self.input_path).parent / error_filename
                error_filepath.parent.mkdir(parents=True, exist_ok=True)
                with open(error_filepath, 'w', encoding='utf-8') as f:
                    f.write(f"# 🔴 EML Conversion Failure\n\n")
                    f.write(f"**File:** `{eml_file.name}`\n\n")
                    f.write(f"**Error:** A catastrophic failure occurred during parsing that could not be gracefully handled.\n\n")
                    f.write("### Exception Details\n\n")
                    f.write(f"**Type:** `{type(e).__name__}`\n\n")
                    f.write(f"**Message:**\n```\n{e}\n```\n\n")
                    f.write(f"**Traceback:**\n```\n{traceback.format_exc()}\n```\n")
        
        return emails, total_files

    def _build_threads(self, emails: List[EmailMessage]):
        """Group emails into conversation threads."""
        emails_by_dir = defaultdict(list)
        for email_msg in emails:
            relative_dir = email_msg.source_path.relative_to(self.input_path)
            emails_by_dir[relative_dir].append(email_msg)
        
        for email_dir, dir_emails in emails_by_dir.items():
            message_id_to_email = {email_msg.message_id: email_msg for email_msg in dir_emails}
            self.threads_by_path[email_dir] = {}
            
            for email_msg in dir_emails:
                thread_id = self._find_or_create_thread(email_msg, message_id_to_email, email_dir)
                if thread_id not in self.threads_by_path[email_dir]:
                    self.threads_by_path[email_dir][thread_id] = EmailThread(email_msg.subject)
                self.threads_by_path[email_dir][thread_id].add_email(email_msg)

    def _find_or_create_thread(self, email_msg: EmailMessage, message_id_map: Dict[str, EmailMessage], email_dir: Path) -> str:
        """Find existing thread or create new one for this email."""
        thread_map = self.threads_by_path.get(email_dir, {})

        # Ensure references is always a list to handle malformed headers
        references = email_msg.references or []
        if isinstance(references, str):
            references = [references]
            
        search_ids = [email_msg.in_reply_to] + references
        for msg_id in filter(None, search_ids):
            if msg_id in message_id_map:
                for tid, thread in thread_map.items():
                    if any(e.message_id == msg_id for e in thread.emails):
                        return tid
        
        for tid, thread in thread_map.items():
            if thread.subject.lower() == email_msg.subject.lower():
                return tid
        
        return email_msg.message_id

    def _generate_output(self):
        """Generate thread files and extract attachments."""
        for email_dir, threads in self.threads_by_path.items():
            output_subdir = self.output_path / email_dir
            output_subdir.mkdir(parents=True, exist_ok=True)
            attachment_manager = AttachmentManager(output_subdir)
            
            for thread in threads.values():
                self._write_thread_file(thread, output_subdir)
                self._extract_thread_attachments(thread, attachment_manager)

    def _write_thread_file(self, thread: EmailThread, output_dir: Path):
        """Write a single thread to a Markdown file."""
        file_path = output_dir / thread.get_thread_filename()
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"# {thread.subject}\n\n")
                participants = {e.from_addr for e in thread.emails if e.from_addr}
                f.write(f"**Participants:** {len(participants)}\n")
                f.write(f"**Emails:** {len(thread.emails)}\n")
                
                # Add source file traceability information
                if thread.source_filenames:
                    f.write(f"**Source Files:** {', '.join(thread.source_filenames)}\n")
                
                f.write(f"\n---\n\n")
                
                for i, email_msg in enumerate(thread.emails):
                    f.write(f"## Email {i+1} of {len(thread.emails)}\n\n")
                    f.write(f"**From:** {email_msg.from_addr or 'Unknown'}\n")
                    f.write(f"**To:** {email_msg.to_addr or 'Unknown'}\n")
                    f.write(f"**Date:** {email_msg.date.strftime('%Y-%m-%d %H:%M')}\n\n")
                    
                    content = email_msg.remove_quoted_text()
                    if content:
                        f.write("### Message\n\n")
                        f.write(content)
                    else:
                        f.write("*No message body found.*")
                    
                    if i < len(thread.emails) - 1:
                        f.write("\n\n---\n\n")
        except Exception as e:
            log_with_thread_info('error', f"💥 THREAD_FILE_WRITE_FAILED: {file_path} | {e}")

    def _extract_thread_attachments(self, thread: EmailThread, attachment_manager: AttachmentManager):
        """Extract all attachments from a thread."""
        for email_msg in thread.emails:
            for filename, content, _ in email_msg.attachments:
                try:
                    attachment_manager.save_attachment(filename, content)
                except Exception as e:
                    log_with_thread_info('warning', f"💥 ATTACHMENT_SAVE_FAILED: {filename} | {e}")