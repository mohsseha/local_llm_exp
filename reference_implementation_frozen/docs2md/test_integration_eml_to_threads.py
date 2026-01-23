import unittest
import tempfile
import base64
import json
from pathlib import Path
from email.mime.text import MIMEText



from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.utils import formatdate, make_msgid
from datetime import datetime, timezone

from eml_to_threads import EmlToThreadsConverter

class TestEmlIntegration(unittest.TestCase):
    """Integration tests for EML to threads conversion focusing on basic functionality and failure modes."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.input_path = Path(self.temp_dir.name) / "input"
        self.output_path = Path(self.temp_dir.name) / "output"
        self.input_path.mkdir()
        self.output_path.mkdir()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_eml_file(self, filename, subject, from_addr, to_addr, msg_id, body=None, html_body=None, date=None, in_reply_to=None, references=None, attachments=None, inline_images=None):
        """Creates and saves a complete .eml file, supporting plain text, HTML, and multipart messages."""
        if not body and not html_body:
            raise ValueError("Either body or html_body must be provided.")

        msg = MIMEMultipart('mixed')
        msg['Subject'] = subject
        msg['From'] = from_addr
        msg['To'] = to_addr
        msg['Date'] = date or formatdate(localtime=True)
        msg['Message-ID'] = msg_id
        if in_reply_to: msg['In-Reply-To'] = in_reply_to
        if references: msg['References'] = references

        # The main content part
        content_part = None
        if body and html_body:
            content_part = MIMEMultipart('alternative')
            content_part.attach(MIMEText(body, 'plain', 'utf-8'))
            content_part.attach(MIMEText(html_body, 'html', 'utf-8'))
        elif body:
            content_part = MIMEText(body, 'plain', 'utf-8')
        else: # html_body
            content_part = MIMEText(html_body, 'html', 'utf-8')

        if inline_images:
            related_part = MIMEMultipart('related')
            related_part.attach(content_part)
            for cid, content in inline_images.items():
                img = MIMEImage(content)
                img.add_header('Content-ID', f'<{cid}>')
                img.add_header('Content-Disposition', 'inline')
                related_part.attach(img)
            msg.attach(related_part)
        else:
            msg.attach(content_part)

        if attachments:
            for att_name, att_content in attachments.items():
                part = MIMEApplication(att_content, Name=att_name)
                part['Content-Disposition'] = f'attachment; filename="{att_name}"'
                msg.attach(part)

        eml_path = self.input_path / filename
        with open(eml_path, 'w', encoding='utf-8') as f:
            f.write(msg.as_string())

    def test_basic_single_email_conversion(self):
        """Test conversion of a single email to markdown."""
        msg_id = make_msgid()
        self._create_eml_file(
            filename="single_email.eml",
            subject="Basic Test Email",
            from_addr="sender@example.com",
            to_addr="recipient@example.com",
            msg_id=msg_id,
            body="This is a basic test email."
        )

        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        result = converter.convert()

        # Basic success assertions - just verify it doesn't crash
        self.assertEqual(result['total_files'], 1)
        self.assertEqual(result['successful_files'], 1)
        self.assertEqual(result['failed_files'], 0)
        self.assertEqual(result['threads_created'], 1)
        
        # Verify at least one markdown file was created
        md_files = list(self.output_path.glob('*.md'))
        self.assertGreaterEqual(len(md_files), 1)

    def test_email_thread_conversation(self):
        """Test conversion of a basic email thread."""
        # First email in thread
        thread1_msg1_id = make_msgid()
        self._create_eml_file(
            filename="thread_email1.eml",
            subject="Thread Test",
            from_addr="alice@example.com",
            to_addr="bob@example.com",
            msg_id=thread1_msg1_id,
            body="Starting a conversation.",
            date=formatdate(1672531200)  # Jan 1, 2023
        )

        # Reply in same thread
        thread1_msg2_id = make_msgid()
        self._create_eml_file(
            filename="thread_email2.eml",
            subject="Re: Thread Test",
            from_addr="bob@example.com",
            to_addr="alice@example.com",
            msg_id=thread1_msg2_id,
            body="Replying to the conversation.",
            date=formatdate(1672617600),  # Jan 2, 2023
            in_reply_to=thread1_msg1_id,
            references=thread1_msg1_id
        )

        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        result = converter.convert()

        # Basic success assertions
        self.assertEqual(result['total_files'], 2)
        self.assertEqual(result['successful_files'], 2)
        self.assertEqual(result['failed_files'], 0)
        self.assertEqual(result['threads_created'], 1)  # Should be grouped into one thread

    def test_multiple_separate_threads(self):
        """Test handling of multiple independent email threads."""
        # Thread 1
        msg1_id = make_msgid()
        self._create_eml_file(
            filename="thread1.eml",
            subject="Thread One Topic",
            from_addr="alice@example.com",
            to_addr="bob@example.com",
            msg_id=msg1_id,
            body="First thread message."
        )

        # Thread 2 - completely separate
        msg2_id = make_msgid()
        self._create_eml_file(
            filename="thread2.eml",
            subject="Thread Two Topic",
            from_addr="charlie@example.com",
            to_addr="diana@example.com",
            msg_id=msg2_id,
            body="Second thread message."
        )

        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        result = converter.convert()

        # Should create separate threads
        self.assertEqual(result['total_files'], 2)
        self.assertEqual(result['successful_files'], 2)
        self.assertEqual(result['failed_files'], 0)
        self.assertEqual(result['threads_created'], 2)

    def test_email_with_attachment(self):
        """Test handling of email with attachment."""
        msg_id = make_msgid()
        self._create_eml_file(
            filename="email_with_attachment.eml",
            subject="Email With File",
            from_addr="sender@example.com",
            to_addr="recipient@example.com",
            msg_id=msg_id,
            body="Please find attached file.",
            attachments={"test_file.txt": b"Test attachment content"}
        )

        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        result = converter.convert()

        # Basic success - should not fail due to attachment
        self.assertEqual(result['total_files'], 1)
        self.assertEqual(result['successful_files'], 1)
        self.assertEqual(result['failed_files'], 0)
        self.assertEqual(result['threads_created'], 1)

    def test_unicode_content_handling(self):
        """Test handling of emails with unicode characters."""
        msg_id = make_msgid()
        self._create_eml_file(
            filename="unicode_email.eml",
            subject="Testing Unicode 🚀 Content",
            from_addr="unicode@example.com",
            to_addr="test@example.com",
            msg_id=msg_id,
            body="Email with unicode: café, résumé, 中文, emoji 🎉"
        )

        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        result = converter.convert()

        # Should handle unicode without crashing
        self.assertEqual(result['total_files'], 1)
        self.assertEqual(result['successful_files'], 1)
        self.assertEqual(result['failed_files'], 0)
        self.assertEqual(result['threads_created'], 1)

    def test_malformed_email_graceful_handling(self):
        """Test graceful handling of malformed email files."""
        # Create a malformed .eml file
        malformed_path = self.input_path / "malformed.eml"
        with open(malformed_path, 'w') as f:
            f.write("This is not a valid email format\n")
            f.write("Missing proper headers\n")
            f.write("Should cause parsing issues but not crash\n")

        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        result = converter.convert()

        # Should handle gracefully - either succeed with degraded parsing or fail gracefully
        self.assertEqual(result['total_files'], 1)
        # Allow either success with graceful degradation or controlled failure
        self.assertTrue(result['successful_files'] + result['failed_files'] == 1)

    def test_empty_input_directory(self):
        """Test behavior with no .eml files."""
        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        result = converter.convert()

        self.assertEqual(result['total_files'], 0)
        self.assertEqual(result['successful_files'], 0)
        self.assertEqual(result['failed_files'], 0)
        self.assertEqual(result['threads_created'], 0)

    def test_processing_doesnt_crash_on_complex_scenario(self):
        """Comprehensive test with various email scenarios to catch failure modes."""
        # Create diverse email scenarios
        scenarios = [
            ("normal.eml", "Normal Email", "normal@test.com", "Basic email content"),
            ("reply.eml", "Re: Normal Email", "reply@test.com", "This is a reply"),
            ("unicode.eml", "Unicode Test 🚀", "unicode@test.com", "Content with émojis and açcénts"),
            ("attachment.eml", "With Attachment", "files@test.com", "See attached file"),
        ]

        msg_ids = []
        for i, (filename, subject, from_addr, body) in enumerate(scenarios):
            msg_id = make_msgid()
            msg_ids.append(msg_id)
            
            attachments = {"test.txt": b"attachment data"} if "attachment" in filename else None
            references = msg_ids[0] if i > 0 else None
            
            self._create_eml_file(
                filename=filename,
                subject=subject,
                from_addr=from_addr,
                to_addr="recipient@test.com",
                msg_id=msg_id,
                body=body,
                references=references,
                attachments=attachments
            )

        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        result = converter.convert()

        # Main goal: doesn't crash and processes files
        self.assertEqual(result['total_files'], 4)
        # Should successfully process most or all files
        self.assertGreaterEqual(result['successful_files'], 3)
        # Should create at least some threads
        self.assertGreaterEqual(result['threads_created'], 1)

    def test_deeply_nested_email_thread(self):
        """Test handling of deeply nested email thread with complex references."""
        msg_ids = []
        
        # Create a 10-email deep thread
        for i in range(10):
            msg_id = make_msgid()
            msg_ids.append(msg_id)
            
            subject = "Initial Discussion" if i == 0 else f"Re: Initial Discussion (#{i})"
            references = ' '.join(msg_ids[:-1]) if i > 0 else None
            in_reply_to = msg_ids[-2] if i > 0 else None
            
            self._create_eml_file(
                filename=f"deep_thread_{i+1:02d}.eml",
                subject=subject,
                from_addr=f"user{i % 3}@company.com",  # Rotate between 3 users
                to_addr="team@company.com",
                msg_id=msg_id,
                body=f"This is message {i+1} in a deep thread discussion.",
                date=formatdate(1672531200 + i * 3600),  # 1 hour apart each
                references=references,
                in_reply_to=in_reply_to
            )
        
        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        result = converter.convert()
        
        # Should handle deep nesting without issues
        self.assertEqual(result['total_files'], 10)
        self.assertGreaterEqual(result['successful_files'], 8)  # Allow some tolerance
        self.assertEqual(result['threads_created'], 1)  # Should be one thread

    def test_massive_email_volume(self):
        """Test handling of large volume of emails to stress test the converter."""
        num_emails = 50
        num_threads = 5
        
        for thread_idx in range(num_threads):
            thread_msg_ids = []
            for email_idx in range(num_emails // num_threads):
                msg_id = make_msgid()
                thread_msg_ids.append(msg_id)
                
                is_first = email_idx == 0
                subject = f"Thread {thread_idx + 1} Topic" if is_first else f"Re: Thread {thread_idx + 1} Topic"
                references = ' '.join(thread_msg_ids[:-1]) if not is_first else None
                
                self._create_eml_file(
                    filename=f"mass_thread{thread_idx}_{email_idx:02d}.eml",
                    subject=subject,
                    from_addr=f"sender{email_idx % 10}@bigcorp.com",
                    to_addr="masslist@bigcorp.com",
                    msg_id=msg_id,
                    body=f"Mass email {email_idx + 1} in thread {thread_idx + 1}.",
                    references=references
                )
        
        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        result = converter.convert()
        
        # Should handle volume without crashing
        self.assertEqual(result['total_files'], num_emails)
        self.assertGreaterEqual(result['successful_files'], num_emails * 0.8)  # 80% success minimum
        self.assertGreaterEqual(result['threads_created'], num_threads - 1)  # Allow some variance

    def test_complex_attachment_scenarios(self):
        """Test various complex attachment scenarios."""
        # Large binary attachment
        large_binary = b'\x89PNG\r\n\x1a\n' + b'\x00' * 10000  # Fake PNG header + large data
        
        # Multiple attachments with same name
        scenarios = [
            ("large_binary.eml", "Large Binary", {"image.png": large_binary}),
            ("multiple_same.eml", "Multiple Same Names", {
                "report.pdf": b"PDF content 1",
                "report.pdf": b"PDF content 2"  # Same filename
            }),
            ("special_chars.eml", "Special Filenames", {
                "file with spaces.txt": b"spaces content",
                "файл.txt": b"cyrillic content",
                "file@#$%.doc": b"special chars content"
            }),
            ("empty_attachments.eml", "Empty Attachments", {
                "empty1.txt": b"",
                "empty2.bin": b"",
                "nonempty.txt": b"has content"
            })
        ]
        
        for filename, subject, attachments in scenarios:
            msg_id = make_msgid()
            self._create_eml_file(
                filename=filename,
                subject=subject,
                from_addr="attach@test.com",
                to_addr="receive@test.com",
                msg_id=msg_id,
                body="Email with complex attachments.",
                attachments=attachments
            )
        
        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        result = converter.convert()
        
        # Should handle complex attachments gracefully
        self.assertEqual(result['total_files'], 4)
        self.assertGreaterEqual(result['successful_files'], 3)
        self.assertGreaterEqual(result['threads_created'], 1)

    def test_corrupted_and_incomplete_emails(self):
        """Test handling of various corrupted and incomplete email formats."""
        # Create various corrupted email files
        corruption_cases = [
            ("truncated_headers.eml", "Subject: Truncated\nFrom: test@"),  # Incomplete
            ("missing_body.eml", "Subject: Missing Body\nFrom: test@test.com\nTo: other@test.com\n\n"),
            ("binary_corruption.eml", "Subject: Binary\nFrom: test@test.com\n\n\x00\x01\x02\xff\xfe\xfd"),
            ("malformed_headers.eml", "Subject Malformed Header\nFrom test@test.com no colon\nTo: other@test.com\n\nBody"),
            ("encoding_issues.eml", "Subject: =?UTF-8?B?VW5rbm93biBFbmNvZGluZw==?=\nFrom: test@test.com\nTo: other@test.com\n\nBody with \xff\xfe bad encoding")
        ]
        
        for filename, content in corruption_cases:
            filepath = self.input_path / filename
            with open(filepath, 'wb') as f:  # Write as binary to preserve corruption
                f.write(content.encode('utf-8', errors='ignore'))
        
        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        result = converter.convert()
        
        # Should handle corruption gracefully without crashing
        self.assertEqual(result['total_files'], 5)
        # Allow failures but ensure it doesn't crash entirely
        self.assertTrue(result['successful_files'] + result['failed_files'] == 5)

    def test_extreme_unicode_and_encoding_scenarios(self):
        """Test extreme unicode and encoding scenarios."""
        extreme_cases = [
            ("mixed_encodings.eml", "Mixed Encodings 🌍", "sender@тест.рф", "Содержимое: café, 北京, العربية, 🎉🚀🌟"),
            ("rtl_content.eml", "RTL Content", "rtl@test.com", "العربية: مرحبا بكم في العالم العربي والإسلامي"),
            ("cjk_content.eml", "CJK Content", "cjk@test.com", "中文测试: 这是一个中文测试邮件。日本語: こんにちは世界。한국어: 안녕하세요 세계."),
            ("emoji_overload.eml", "🎉🚀🌟💻📧🔥⚡🎯🌈🎊", "emoji@test.com", "🎉🚀🌟💻📧🔥⚡🎯🌈🎊" * 100),  # Emoji spam
            ("zero_width.eml", "Zero Width Test", "zw@test.com", "Text\u200bwith\u200bzero\u200bwidth\u200bspaces")
        ]
        
        for filename, subject, from_addr, body in extreme_cases:
            msg_id = make_msgid()
            self._create_eml_file(
                filename=filename,
                subject=subject,
                from_addr=from_addr,
                to_addr="unicode@test.com",
                msg_id=msg_id,
                body=body
            )
        
        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        result = converter.convert()
        
        # Should handle extreme unicode without crashing
        self.assertEqual(result['total_files'], 5)
        self.assertGreaterEqual(result['successful_files'], 4)  # Allow one failure
        self.assertGreaterEqual(result['threads_created'], 1)

    def test_complex_threading_edge_cases(self):
        """Test complex threading scenarios that might confuse the algorithm."""
        # Scenario 1: Circular references (shouldn't happen but test robustness)
        msg1_id = make_msgid()
        msg2_id = make_msgid()
        msg3_id = make_msgid()
        
        # Create emails with circular-like references
        self._create_eml_file(
            filename="circular_1.eml",
            subject="Circular Test 1",
            from_addr="c1@test.com",
            to_addr="team@test.com",
            msg_id=msg1_id,
            body="First in potential circular chain."
        )
        
        self._create_eml_file(
            filename="circular_2.eml",
            subject="Re: Circular Test 1",
            from_addr="c2@test.com",
            to_addr="team@test.com",
            msg_id=msg2_id,
            body="Second in chain.",
            references=msg1_id
        )
        
        self._create_eml_file(
            filename="circular_3.eml",
            subject="Re: Circular Test 1",
            from_addr="c3@test.com",
            to_addr="team@test.com",
            msg_id=msg3_id,
            body="Third references both.",
            references=f"{msg1_id} {msg2_id}"
        )
        
        # Scenario 2: Same subject, different conversations
        base_subject = "Weekly Status"
        for i in range(3):
            msg_id = make_msgid()
            self._create_eml_file(
                filename=f"same_subject_{i+1}.eml",
                subject=base_subject,
                from_addr=f"person{i}@different-company-{i}.com",
                to_addr=f"team{i}@different-company-{i}.com",
                msg_id=msg_id,
                body=f"Status from company {i+1}",
                date=formatdate(1672531200 + i * 86400)  # Different days
            )
        
        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        result = converter.convert()
        
        # Should handle edge cases without crashing
        self.assertEqual(result['total_files'], 6)
        self.assertGreaterEqual(result['successful_files'], 5)
        self.assertGreaterEqual(result['threads_created'], 2)  # At least some threading logic

    def test_subdirectory_structure_processing(self):
        """Test processing emails in nested subdirectory structures."""
        # Create nested directory structure
        subdirs = [
            self.input_path / "project_a" / "2023" / "q1",
            self.input_path / "project_b" / "2023" / "q2", 
            self.input_path / "urgent",
            self.input_path / "archive" / "old_project"
        ]
        
        for subdir in subdirs:
            subdir.mkdir(parents=True, exist_ok=True)
        
        # Create emails in different subdirectories
        dir_emails = [
            (subdirs[0], "proj_a_q1.eml", "Project A Q1 Update"),
            (subdirs[0], "proj_a_q1_reply.eml", "Re: Project A Q1 Update"),
            (subdirs[1], "proj_b_q2.eml", "Project B Q2 Planning"),
            (subdirs[2], "urgent_issue.eml", "URGENT: Server Down"),
            (subdirs[3], "old_discussion.eml", "Old Project Discussion")
        ]
        
        msg_ids = []
        for i, (directory, filename, subject) in enumerate(dir_emails):
            msg_id = make_msgid()
            msg_ids.append(msg_id)
            
            # Make second email a reply to first in same directory
            is_reply = "reply" in filename
            references = msg_ids[0] if is_reply else None
            
            msg = MIMEMultipart()
            msg['Subject'] = subject
            msg['From'] = f"user{i}@company.com"
            msg['To'] = "team@company.com"
            msg['Date'] = formatdate(localtime=True)
            msg['Message-ID'] = msg_id
            if references:
                msg['References'] = references
                msg['In-Reply-To'] = references
            
            msg.attach(MIMEText(f"Content for {subject}", 'plain', 'utf-8'))
            
            eml_path = directory / filename
            with open(eml_path, 'w') as f:
                f.write(msg.as_string())
        
        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        result = converter.convert()
        
        # Should process nested structure successfully
        self.assertEqual(result['total_files'], 5)
        self.assertGreaterEqual(result['successful_files'], 4)
        self.assertGreaterEqual(result['threads_created'], 3)  # At least some separation
        
        # Verify nested output structure is created
        self.assertTrue((self.output_path / "project_a" / "2023" / "q1").exists())
        self.assertTrue((self.output_path / "urgent").exists())

    def test_date_and_timezone_edge_cases(self):
        """Test various date and timezone scenarios."""
        date_scenarios = [
            ("future_date.eml", "Future Email", formatdate(2147483647)),  # Year 2038
            ("past_date.eml", "Ancient Email", formatdate(0)),  # Unix epoch
            ("no_date.eml", "No Date", None),  # Missing date
            ("invalid_date.eml", "Invalid Date", "Not a valid date string"),
            ("tz_plus.eml", "Timezone Plus", "Mon, 01 Jan 2023 12:00:00 +0800"),
            ("tz_minus.eml", "Timezone Minus", "Mon, 01 Jan 2023 12:00:00 -0500"),
            ("tz_utc.eml", "UTC Time", "Mon, 01 Jan 2023 12:00:00 GMT")
        ]
        
        for filename, subject, date_str in date_scenarios:
            msg = MIMEMultipart()
            msg['Subject'] = subject
            msg['From'] = "dates@test.com"
            msg['To'] = "time@test.com"
            msg['Message-ID'] = make_msgid()
            
            if date_str and date_str != "Not a valid date string":
                msg['Date'] = date_str
            elif date_str == "Not a valid date string":
                msg['Date'] = date_str  # Invalid date format
            # else: no date header
            
            msg.attach(MIMEText(f"Email with date scenario: {subject}", 'plain', 'utf-8'))
            
            eml_path = self.input_path / filename
            with open(eml_path, 'w') as f:
                f.write(msg.as_string())
        
        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        result = converter.convert()
        
        # Should handle date edge cases gracefully
        self.assertEqual(result['total_files'], 7)
        self.assertGreaterEqual(result['successful_files'], 5)  # Allow some tolerance for edge cases
        self.assertGreaterEqual(result['threads_created'], 1)

    def test_html_email_conversion_scenarios(self):
        """Test various HTML email conversion scenarios for reliability."""
        # Scenario 1: Simple HTML-only email
        html_only_body = "<h1>Test HTML</h1><p>This is a <b>bold</b> test.</p>"
        self._create_eml_file(
            filename="html_only.eml",
            subject="HTML Only Email",
            from_addr="html@example.com",
            to_addr="recipient@example.com",
            msg_id=make_msgid(),
            html_body=html_only_body
        )

        # Scenario 2: Multipart (plain + HTML) email
        plain_body_multi = "This is the plain text version."
        html_body_multi = "<h1>Multipart Test</h1><p>This is the <i>HTML</i> version.</p>"
        self._create_eml_file(
            filename="multipart.eml",
            subject="Multipart/Alternative Email",
            from_addr="multipart@example.com",
            to_addr="recipient@example.com",
            msg_id=make_msgid(),
            body=plain_body_multi,
            html_body=html_body_multi
        )

        # Scenario 3: HTML with inline image
        # Create a simple 1x1 red pixel PNG
        red_pixel_png = base64.b64decode(b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/wcAAwAB/epv2AAAAABJRU5ErkJggg==')
        html_with_inline_img = '<h1>Inline Image</h1><p>Here is an image: <img src="cid:red_pixel"></p>'
        self._create_eml_file(
            filename="inline_image.eml",
            subject="HTML with Inline Image",
            from_addr="inline@example.com",
            to_addr="recipient@example.com",
            msg_id=make_msgid(),
            body="Plain text with inline image.",
            html_body=html_with_inline_img,
            inline_images={"red_pixel": red_pixel_png}
        )

        # Scenario 4: Complex HTML with CSS and tables
        complex_html = """
        <html>
          <head>
            <style>
              .blue { color: blue; }
              table { border-collapse: collapse; }
              td, th { border: 1px solid black; padding: 5px; }
            </style>
          </head>
          <body>
            <h1 class="blue">Complex HTML Test</h1>
            <p>This email contains CSS and a table.</p>
            <table>
              <tr><th>Header 1</th><th>Header 2</th></tr>
              <tr><td>Data 1</td><td>Data 2</td></tr>
            </table>
          </body>
        </html>
        """
        self._create_eml_file(
            filename="complex_html.eml",
            subject="Complex HTML Structure",
            from_addr="complex@example.com",
            to_addr="recipient@example.com",
            msg_id=make_msgid(),
            html_body=complex_html
        )

        # Scenario 5: Malformed HTML
        malformed_html = "<h1>This is a test</h3><p>Mismatched tags and unclosed elements.<br>"
        self._create_eml_file(
            filename="malformed_html.eml",
            subject="Malformed HTML",
            from_addr="malformed@example.com",
            to_addr="recipient@example.com",
            msg_id=make_msgid(),
            html_body=malformed_html
        )

        # Scenario 6: Nasty complex HTML with heavy inline CSS
        complex_css_html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Complex HTML Email</title>
            <style>
                @media screen and (max-width: 600px) {
                    .container { width: 100% !important; }
                    .column { width: 100% !important; display: block !important; margin-bottom: 20px !important; }
                }
            </style>
        </head>
        <body style="margin: 0; padding: 0; background-color: #f4f4f4;">
            <table border="0" cellpadding="0" cellspacing="0" width="100%">
                <tr>
                    <td align="center" style="padding: 20px 0;">
                        <table class="container" border="0" cellpadding="0" cellspacing="0" width="600" style="background-color: #ffffff;">
                            <tr>
                                <td align="center" style="padding: 40px 0;">
                                    <img src="https://via.placeholder.com/150" alt="Logo" width="150">
                                </td>
                            </tr>
                            <tr>
                                <td align="center" style="padding: 20px;">
                                    <h1 style="font-family: Arial, sans-serif; color: #333333;">Welcome!</h1>
                                    <p style="font-family: Arial, sans-serif; color: #666666; line-height: 1.6;">
                                        Lorem ipsum dolor sit amet, consectetur adipiscing elit.
                                    </p>
                                    <a href="#" style="display: inline-block; background-color: #007bff; color: #ffffff; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-family: Arial, sans-serif; margin-top: 20px;">Call to Action</a>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 40px 20px;">
                                    <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                        <tr>
                                            <td class="column" width="33.33%" align="center" style="padding: 0 10px;">
                                                <img src="https://via.placeholder.com/100" alt="Feature 1" width="100">
                                                <h3 style="font-family: Arial, sans-serif; color: #333333;">Feature One</h3>
                                            </td>
                                            <td class="column" width="33.33%" align="center" style="padding: 0 10px;">
                                                <img src="https://via.placeholder.com/100" alt="Feature 2" width="100">
                                                <h3 style="font-family: Arial, sans-serif; color: #333333;">Feature Two</h3>
                                            </td>
                                            <td class="column" width="33.33%" align="center" style="padding: 0 10px;">
                                                <img src="https://via.placeholder.com/100" alt="Feature 3" width="100">
                                                <h3 style="font-family: Arial, sans-serif; color: #333333;">Feature Three</h3>
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>
                            <tr>
                                <td align="center" style="padding: 40px 20px; background-color: #333333; color: #ffffff;">
                                    <p style="font-family: Arial, sans-serif;">&copy; 2024 Your Company.</p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
        self._create_eml_file(
            filename="nasty_html_css.eml",
            subject="Complex CSS and HTML Email",
            from_addr="nasty@example.com",
            to_addr="recipient@example.com",
            msg_id=make_msgid(),
            html_body=complex_css_html
        )

        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        result = converter.convert()

        # Assert that all files were processed without crashing
        self.assertEqual(result['total_files'], 6)
        self.assertGreaterEqual(result['successful_files'], 5) # Allow for graceful failure on malformed
        self.assertEqual(result['successful_files'] + result['failed_files'], 6)
        self.assertGreaterEqual(result['threads_created'], 1)

        # Verify that an inline image was saved
        # Note: The exact filename will depend on the converter's implementation
        self.assertTrue(any(p.name.startswith('red_pixel') for p in self.output_path.iterdir()))

    def test_nightmare_attachment_thread_scenario(self):
        """End-to-end test with complex threading plus nightmare attachment scenarios."""
        # Create a thread with escalating attachment complexity
        msg_ids = []
        attachment_scenarios = [
            # Email 1: Normal start
            {"filename": "start.txt", "content": b"Project kickoff document"},
            
            # Email 2: Multiple attachments with same names
            {
                "report.pdf": b"First PDF version",
                "report.pdf": b"Second PDF version (should conflict)",
                "report.docx": b"Word document version"
            },
            
            # Email 3: Massive binary attachment + unicode filenames
            {
                "ファイル.テキスト": b"Japanese filename",  # Japanese
                "café_élève.pdf": b"French accented filename",  # French accents
                "massive_binary.bin": b"\x89PNG\r\n\x1a\n" + b"\x00" * 50000  # 50KB binary
            },
            
            # Email 4: Special character nightmare
            {
                "file with spaces and !@#$%^&*()_+{}[]:;'<>?,./~`": b"special chars",
                "": b"empty filename",  # Empty filename
                "\x00\x01\x02.bin": b"null bytes in name"  # Null bytes
            },
            
            # Email 5: Corrupted/empty attachments
            {
                "empty1.txt": b"",  # Zero bytes
                "empty2.bin": b"",  # Zero bytes
                "corrupted.zip": b"PK\x03\x04" + b"\xff" * 1000,  # Fake ZIP header + garbage
            }
        ]
        
        for i, attachments in enumerate(attachment_scenarios):
            msg_id = make_msgid()
            msg_ids.append(msg_id)
            
            subject = "Project Discussion" if i == 0 else f"Re: Project Discussion (Round {i+1})"
            references = ' '.join(msg_ids[:-1]) if i > 0 else None
            in_reply_to = msg_ids[-2] if i > 0 else None
            
            self._create_eml_file(
                filename=f"nightmare_thread_{i+1:02d}.eml",
                subject=subject,
                from_addr=f"chaos{i}@nightmare.com",
                to_addr="victims@nightmare.com",
                msg_id=msg_id,
                body=f"Email {i+1} with {len(attachments)} attachment(s). This is getting complex!",
                date=formatdate(1672531200 + i * 3600),
                references=references,
                in_reply_to=in_reply_to,
                attachments=attachments
            )
        
        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        result = converter.convert()
        
        # End-to-end verification: should handle nightmare scenario
        self.assertEqual(result['total_files'], 5)
        self.assertGreaterEqual(result['successful_files'], 4)  # Allow one failure
        self.assertEqual(result['threads_created'], 1)  # Should be one thread
        
        # Verify at least some attachments were saved (even if some fail)
        attachment_files = list(self.output_path.glob('**/*'))
        non_md_files = [f for f in attachment_files if f.suffix != '.md' and f.is_file()]
        self.assertGreater(len(non_md_files), 3)  # At least some attachments saved

    def test_interleaved_threads_with_attachments(self):
        """Test multiple interleaved threads each with different attachment types."""
        # Thread A: Image attachments
        thread_a_msgs = []
        for i in range(3):
            msg_id = make_msgid()
            thread_a_msgs.append(msg_id)
            
            # Create fake image data
            fake_png = b"\x89PNG\r\n\x1a\n" + b"fake png data" + b"\x00" * (1000 * (i+1))
            fake_jpg = b"\xff\xd8\xff\xe0" + b"fake jpg data" + b"\x00" * (500 * (i+1))
            
            attachments = {
                f"screenshot_{i+1}.png": fake_png,
                f"photo_{i+1}.jpg": fake_jpg
            } if i > 0 else {"initial_image.png": fake_png}
            
            subject = "Image Thread" if i == 0 else f"Re: Image Thread (Image {i+1})"
            references = ' '.join(thread_a_msgs[:-1]) if i > 0 else None
            
            self._create_eml_file(
                filename=f"thread_a_img_{i+1}.eml",
                subject=subject,
                from_addr=f"photographer{i}@visual.com",
                to_addr="gallery@visual.com",
                msg_id=msg_id,
                body=f"Here are the images for review #{i+1}",
                references=references,
                attachments=attachments
            )
        
        # Thread B: Document attachments with version conflicts
        thread_b_msgs = []
        for i in range(4):
            msg_id = make_msgid()
            thread_b_msgs.append(msg_id)
            
            # Same filename, different content (version conflict)
            doc_content = f"Document version {i+1}\n" + "Content " * (100 * (i+1))
            
            attachments = {
                "project_spec.docx": doc_content.encode('utf-8'),
                "project_spec.pdf": f"PDF version {i+1}".encode('utf-8'),
                f"revision_notes_v{i+1}.txt": f"Changes in version {i+1}".encode('utf-8')
            }
            
            subject = "Document Review" if i == 0 else f"Re: Document Review v{i+1}"
            references = ' '.join(thread_b_msgs[:-1]) if i > 0 else None
            
            self._create_eml_file(
                filename=f"thread_b_doc_{i+1}.eml",
                subject=subject,
                from_addr=f"editor{i}@docs.com",
                to_addr="reviewers@docs.com",
                msg_id=msg_id,
                body=f"Please review the updated documents (version {i+1})",
                references=references,
                attachments=attachments
            )
        
        # Thread C: Mixed chaos (interleaved with A and B)
        thread_c_msgs = []
        chaos_attachments = [
            {"log_file.txt": b"ERROR: Something went wrong\n" * 1000},
            {
                "backup.zip": b"PK\x03\x04fake_zip_content" + b"\x00" * 2000,
                "config.json": b'{"setting": "value", "array": [1,2,3]}',
                "ファイル.txt": "日本語のテキストファイル".encode('utf-8')
            },
            {"corrupted_file.bin": b"\xff\xfe\xfd" + b"corruption" * 500}
        ]
        
        for i, attachments in enumerate(chaos_attachments):
            msg_id = make_msgid()
            thread_c_msgs.append(msg_id)
            
            subject = "System Issues" if i == 0 else f"Re: System Issues (Update {i+1})"
            references = ' '.join(thread_c_msgs[:-1]) if i > 0 else None
            
            self._create_eml_file(
                filename=f"thread_c_chaos_{i+1}.eml",
                subject=subject,
                from_addr=f"sysadmin{i}@chaos.com",
                to_addr="devteam@chaos.com",
                msg_id=msg_id,
                body=f"System update {i+1} - check attached logs/files",
                references=references,
                attachments=attachments
            )
        
        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        result = converter.convert()
        
        # Should handle multiple complex threads
        self.assertEqual(result['total_files'], 10)  # 3 + 4 + 3
        self.assertGreaterEqual(result['successful_files'], 8)  # Allow some tolerance
        self.assertGreaterEqual(result['threads_created'], 3)  # Should be at least 3 threads (may be more due to threading logic) 
        
        # Verify significant number of attachments were processed
        all_files = list(self.output_path.rglob('*'))
        attachment_files = [f for f in all_files if f.is_file() and f.suffix != '.md']
        self.assertGreater(len(attachment_files), 5)  # Should have some attachments
        
        # Verify thread files exist
        md_files = [f for f in all_files if f.suffix == '.md']
        self.assertGreaterEqual(len(md_files), 3)  # At least 3 threads

    def test_attachment_deduplication_across_threads(self):
        """Test that identical attachments across different emails are deduplicated properly."""
        # Create identical attachment content
        identical_content = b"This is identical content that appears in multiple emails" + b"\x00" * 5000
        
        # Thread 1: Multiple emails with same attachment
        thread1_msgs = []
        for i in range(3):
            msg_id = make_msgid()
            thread1_msgs.append(msg_id)
            
            # Same attachment in each email (should be deduplicated)
            attachments = {
                "shared_file.txt": identical_content,
                f"unique_file_{i}.txt": f"Unique content for email {i}".encode('utf-8')
            }
            
            subject = "Shared Document Thread" if i == 0 else f"Re: Shared Document Thread #{i+1}"
            references = ' '.join(thread1_msgs[:-1]) if i > 0 else None
            
            self._create_eml_file(
                filename=f"dedup_thread1_{i+1}.eml",
                subject=subject,
                from_addr=f"sender{i}@dedup.com",
                to_addr="team@dedup.com",
                msg_id=msg_id,
                body=f"Email {i+1} with shared attachment",
                references=references,
                attachments=attachments
            )
        
        # Thread 2: Different thread, same attachment content
        thread2_msgs = []
        for i in range(2):
            msg_id = make_msgid()
            thread2_msgs.append(msg_id)
            
            # Same identical content, different filename
            attachments = {
                "duplicate_content.doc": identical_content,  # Same content, different name
                f"thread2_file_{i}.pdf": f"Thread 2 unique content {i}".encode('utf-8')
            }
            
            subject = "Another Thread" if i == 0 else "Re: Another Thread"
            references = thread2_msgs[0] if i > 0 else None
            
            self._create_eml_file(
                filename=f"dedup_thread2_{i+1}.eml",
                subject=subject,
                from_addr=f"other{i}@dedup.com",
                to_addr="team@dedup.com",
                msg_id=msg_id,
                body=f"Different thread, email {i+1}",
                references=references,
                attachments=attachments
            )
        
        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        result = converter.convert()
        
        # Should process all emails successfully
        self.assertEqual(result['total_files'], 5)
        self.assertEqual(result['successful_files'], 5)
        self.assertGreaterEqual(result['threads_created'], 2)  # Should be at least 2 threads
        
        # Check deduplication - should have saved some attachments
        all_files = list(self.output_path.rglob('*'))
        attachment_files = [f for f in all_files if f.is_file() and f.suffix != '.md']
        
        # Should have saved some attachments (exact count depends on deduplication logic)
        self.assertGreater(len(attachment_files), 2)  # At least some attachments
        self.assertLess(len(attachment_files), 10)  # But not unlimited

    def test_broken_attachment_encoding_scenarios(self):
        """Test various broken attachment encoding scenarios that should be handled gracefully."""
        broken_scenarios = [
            # Email 1: Invalid base64 in attachment
            {
                "invalid_b64.txt": "not_base64_content!!!",  # String instead of bytes
                "partial_b64.bin": "SGVsbG8gV29ybGQ="  # Valid base64 but as string
            },
            
            # Email 2: Mixed valid/invalid attachments
            {
                "valid.txt": b"Valid binary content",
                "invalid_encoding.pdf": "\xff\xfe\xfd invalid encoding",
                "empty_name": b"Content with empty name above"
            },
            
            # Email 3: Extremely long filenames and content
            {
                ("a" * 300 + ".txt"): b"Long filename content",
                "normal.txt": b"x" * 100000,  # 100KB content
                "unicode_中文_العربية_🚀.bin": b"Mixed unicode filename"
            },
            
            # Email 4: Null bytes and control characters in content
            {
                "null_content.bin": b"\x00\x01\x02\x03" + b"regular content" + b"\xff\xfe\xfd",
                "control_chars.txt": b"\r\n\t\v\f" + "Control chars mixed".encode('utf-8'),
                "mixed_encoding.txt": "Mixed \xff content \x00 with \xfe problems".encode('latin1', errors='ignore')
            }
        ]
        
        msg_ids = []
        for i, attachments in enumerate(broken_scenarios):
            msg_id = make_msgid()
            msg_ids.append(msg_id)
            
            subject = "Broken Encoding Test" if i == 0 else f"Re: Broken Encoding Test #{i+1}"
            references = ' '.join(msg_ids[:-1]) if i > 0 else None
            
            # Manually create email to control attachment encoding issues
            msg = MIMEMultipart()
            msg['Subject'] = subject
            msg['From'] = f"broken{i}@encoding.com"
            msg['To'] = "debug@encoding.com"
            msg['Date'] = formatdate(localtime=True)
            msg['Message-ID'] = msg_id
            if references:
                msg['References'] = references
            
            msg.attach(MIMEText(f"Email {i+1} with broken attachment scenarios", 'plain', 'utf-8'))
            
            # Add attachments with potential encoding issues
            for att_name, att_content in attachments.items():
                try:
                    if isinstance(att_content, str):
                        # Intentionally problematic string attachment
                        part = MIMEApplication(att_content.encode('utf-8', errors='replace'), Name=att_name)
                    else:
                        part = MIMEApplication(att_content, Name=att_name)
                    part['Content-Disposition'] = f'attachment; filename="{att_name}"'
                    msg.attach(part)
                except Exception:
                    # Even adding the attachment fails - create a minimal one
                    part = MIMEApplication(b"fallback content", Name="fallback.txt")
                    part['Content-Disposition'] = 'attachment; filename="fallback.txt"'
                    msg.attach(part)
            
            eml_path = self.input_path / f"broken_encoding_{i+1}.eml"
            with open(eml_path, 'w', encoding='utf-8', errors='replace') as f:
                f.write(msg.as_string())
        
        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        result = converter.convert()
        
        # Should handle broken encodings gracefully without total failure
        self.assertEqual(result['total_files'], 4)
        self.assertGreaterEqual(result['successful_files'], 2)  # Allow failures but not total failure
        self.assertGreaterEqual(result['threads_created'], 1)  # Should form at least one thread
        
        # Should have created some output files despite encoding issues
        all_files = list(self.output_path.rglob('*'))
        self.assertGreater(len(all_files), 1)  # At least thread markdown + some attachments

    def test_massive_thread_with_attachment_evolution(self):
        """End-to-end test of a massive thread where attachment complexity evolves over time."""
        # Simulate a long project thread with evolving attachment complexity
        msg_ids = []
        thread_phases = [
            # Phase 1: Simple start (emails 0-2)
            lambda i: {"brief.txt": f"Phase 1 brief {i}".encode('utf-8')},
            
            # Phase 2: Adding images (emails 3-5)
            lambda i: {
                "brief.txt": f"Phase 2 brief {i}".encode('utf-8'),
                f"mockup_{i}.png": b"\x89PNG\r\n\x1a\n" + f"fake png {i}".encode('utf-8') * 100
            },
            
            # Phase 3: Adding documents (emails 6-8)
            lambda i: {
                "brief.txt": f"Phase 3 brief {i}".encode('utf-8'),
                f"spec_v{i}.docx": f"Document version {i}\n".encode('utf-8') * 200,
                f"diagram_{i}.png": b"\x89PNG\r\n\x1a\n" + b"diagram data" * 50
            },
            
            # Phase 4: Adding code and configs (emails 9-11)
            lambda i: {
                "brief.txt": f"Phase 4 brief {i}".encode('utf-8'),
                f"source_v{i}.py": f"# Python code version {i}\nprint('version {i}')\n".encode('utf-8') * 50,
                f"config_{i}.json": f'{{"version": {i}, "settings": [1,2,3]}}\n'.encode('utf-8'),
                "database.sql": f"-- SQL version {i}\nSELECT * FROM table_{i};\n".encode('utf-8') * 30
            },
            
            # Phase 5: Chaos phase (emails 12-14)
            lambda i: {
                "brief.txt": f"Phase 5 URGENT brief {i}".encode('utf-8'),
                f"hotfix_{i}.patch": f"patch content for issue {i}\n".encode('utf-8') * 100,
                "logs.txt": f"ERROR: Issue {i}\n".encode('utf-8') * 500,
                f"紧急_修复_{i}.txt": f"Chinese emergency fix {i}".encode('utf-8'),
                "corrupted.bin": b"\xff\xfe\xfd" + b"corrupted" * 200
            }
        ]
        
        email_count = 15
        for i in range(email_count):
            msg_id = make_msgid()
            msg_ids.append(msg_id)
            
            # Determine which phase we're in
            phase_idx = min(i // 3, len(thread_phases) - 1)
            attachments = thread_phases[phase_idx](i)
            
            subject = "Project Evolution" if i == 0 else f"Re: Project Evolution (Update {i+1})"
            references = ' '.join(msg_ids[:-1]) if i > 0 else None
            in_reply_to = msg_ids[-2] if i > 0 else None
            
            self._create_eml_file(
                filename=f"evolution_{i+1:02d}.eml",
                subject=subject,
                from_addr=f"dev{i % 5}@evolution.com",  # Rotate through 5 developers
                to_addr="project@evolution.com",
                msg_id=msg_id,
                body=f"Project update {i+1}. Phase {phase_idx + 1}. Complexity is increasing!",
                date=formatdate(1672531200 + i * 7200),  # 2 hours apart
                references=references,
                in_reply_to=in_reply_to,
                attachments=attachments
            )
        
        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        result = converter.convert()
        
        # End-to-end verification of massive thread processing
        self.assertEqual(result['total_files'], email_count)
        self.assertGreaterEqual(result['successful_files'], email_count * 0.8)  # 80% success minimum
        self.assertEqual(result['threads_created'], 1)  # Should be one massive thread
        
        # Verify massive attachment processing
        all_files = list(self.output_path.rglob('*'))
        attachment_files = [f for f in all_files if f.is_file() and f.suffix != '.md']
        self.assertGreater(len(attachment_files), 20)  # Should have many attachments
        
        # Verify the thread markdown file exists and is substantial
        md_files = [f for f in all_files if f.suffix == '.md']
        self.assertEqual(len(md_files), 1)
        
        # Check that the markdown file is substantial (indicates successful processing)
        thread_content = md_files[0].read_text()
        self.assertIn("Project Evolution", thread_content)
        self.assertIn("Emails:", thread_content)
        
        # Should contain multiple email entries
        email_sections = thread_content.count("## Email")
        self.assertGreaterEqual(email_sections, email_count * 0.8)  # Most emails processed

if __name__ == '__main__':
    unittest.main()