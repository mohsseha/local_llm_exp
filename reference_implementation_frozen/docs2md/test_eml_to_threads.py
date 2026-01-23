import unittest
import tempfile
import base64
import mailparser
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from eml_to_threads import EmlToThreadsConverter, EmailMessage

class TestEmlToThreads(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.input_path = Path(self.temp_dir.name) / "input"
        self.output_path = Path(self.temp_dir.name) / "output"
        self.input_path.mkdir()
        self.output_path.mkdir()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_mock_email(self, subject, date, references, in_reply_to, message_id, filename, body=None, defects=None, attachments=None):
        """Creates a mock email object and saves a dummy .eml file."""
        mock_mail = MagicMock()
        mock_mail.subject = subject
        mock_mail.date = date
        mock_mail.references = references
        mock_mail.in_reply_to = in_reply_to
        mock_mail.message_id = message_id
        mock_mail.body = body or f"This is a test email: {subject}"
        mock_mail.attachments = attachments or []
        mock_mail.defects = defects or []
        
        eml_path = self.input_path / filename
        eml_path.touch()
        
        return mock_mail, eml_path

    # --- Existing Tests ---

    @patch('eml_to_threads.mailparser.parse_from_file')
    def test_references_as_string_and_date_normalization(self, mock_parse):
        """Handles 'references' as a string and normalizes mixed-timezone dates."""
        mock_mail_1, path_1 = self._create_mock_email("Test Thread", datetime(2023, 1, 1, 10, 0, 0), [], None, "<id_1@example.com>", "email1.eml")
        mock_mail_2, path_2 = self._create_mock_email("Re: Test Thread", datetime(2023, 1, 1, 11, 0, 0, tzinfo=timezone.utc), "<id_1@example.com>", "<id_1@example.com>", "<id_2@example.com>", "email2.eml")
        
        mock_parse.side_effect = lambda fp: {str(path_1): mock_mail_1, str(path_2): mock_mail_2}.get(fp)

        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        result = converter.convert()

        self.assertEqual(result['threads_created'], 1)
        thread = list(list(converter.threads_by_path.values())[0].values())[0]
        self.assertEqual(len(thread.emails), 2)
        self.assertIsNotNone(thread.emails[1].date.tzinfo)

    @patch('eml_to_threads.mailparser.parse_from_file')
    def test_multiple_distinct_threads(self, mock_parse):
        """Tests that two separate conversations are sorted into two threads."""
        mock_mail_A1, path_A1 = self._create_mock_email("Thread A", datetime.now(timezone.utc), [], None, "<A1>", "A1.eml")
        mock_mail_A2, path_A2 = self._create_mock_email("Re: Thread A", datetime.now(timezone.utc), ["<A1>"], "<A1>", "<A2>", "A2.eml")
        mock_mail_B1, path_B1 = self._create_mock_email("Thread B", datetime.now(timezone.utc), [], None, "<B1>", "B1.eml")
        
        mock_parse.side_effect = lambda fp: {str(path_A1): mock_mail_A1, str(path_A2): mock_mail_A2, str(path_B1): mock_mail_B1}.get(fp)

        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        result = converter.convert()

        self.assertEqual(result['threads_created'], 2)

    @patch('eml_to_threads.mailparser.parse_from_file')
    def test_graceful_failure_on_parsing_error(self, mock_parse):
        """Ensures one failed parse does not stop the processing of other valid emails."""
        mock_mail_ok, path_ok = self._create_mock_email("Good Email", datetime.now(timezone.utc), [], None, "<ok>", "ok.eml")
        path_bad = self.input_path / "bad.eml"; path_bad.touch()

        mock_parse.side_effect = lambda fp: mock_mail_ok if fp == str(path_ok) else (_ for _ in ()).throw(ValueError("Test Failure"))

        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        result = converter.convert()

        self.assertEqual(result['successful_files'], 1)
        self.assertEqual(result['failed_files'], 1)
        self.assertTrue((self.output_path / "bad_conversion_error.md").exists())

    # --- New Outlook & Corporate Corner Case Tests ---

    @patch('eml_to_threads.mailparser.parse_from_file')
    def test_html_email_with_embedded_images(self, mock_parse):
        """Ensures HTML body is extracted and embedded images are saved."""
        html_body = "<html><body><p>Hello World</p><img src='cid:logo.png'></body></html>"
        attachments = [{
            'filename': 'logo.png',
            'payload': base64.b64encode(b'imagedata').decode('ascii'),
            'mail_content_type': 'image/png'
        }]
        mock_mail, path = self._create_mock_email("HTML Email", datetime.now(timezone.utc), [], None, "<html1>", "html.eml", body=html_body, attachments=attachments)
        mock_parse.return_value = mock_mail

        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        converter.convert()

        self.assertTrue((self.output_path / "logo.png").exists())
        self.assertTrue((self.output_path / "logo.png").read_bytes() == b'imagedata')

    @patch('eml_to_threads.mailparser.parse_from_file')
    def test_calendar_invite_attachment(self, mock_parse):
        """Ensures .ics calendar invites are saved as attachments."""
        attachments = [{
            'filename': 'invite.ics',
            'payload': base64.b64encode(b'BEGIN:VCALENDAR...').decode('ascii'),
            'mail_content_type': 'text/calendar'
        }]
        mock_mail, path = self._create_mock_email("Meeting", datetime.now(timezone.utc), [], None, "<ics1>", "invite.eml", attachments=attachments)
        mock_parse.return_value = mock_mail

        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        converter.convert()

        self.assertTrue((self.output_path / "invite.ics").exists())

    @patch('eml_to_threads.mailparser.parse_from_file')
    def test_winmail_dat_extraction(self, mock_parse):
        """Simulates mail-parser extracting files from a TNEF (winmail.dat) attachment."""
        # mail-parser handles this internally. We mock the *result* of that process.
        attachments = [{
            'filename': 'document.docx',
            'payload': base64.b64encode(b'word document data').decode('ascii'),
            'mail_content_type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        }]
        mock_mail, path = self._create_mock_email("From Outlook", datetime.now(timezone.utc), [], None, "<tnef1>", "outlook.eml", attachments=attachments)
        mock_parse.return_value = mock_mail

        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        converter.convert()

        self.assertTrue((self.output_path / "document.docx").exists())

    @patch('eml_to_threads.mailparser.parse_from_file')
    def test_attachment_with_special_characters_in_filename(self, mock_parse):
        """Tests saving attachments with non-ASCII and special filenames."""
        filename = "résumé_für_das_jahr_2023-01-01 (final).pdf"
        attachments = [{'filename': filename, 'payload': base64.b64encode(b'pdfdata').decode('ascii'), 'mail_content_type': 'application/pdf'}]
        mock_mail, path = self._create_mock_email("Special Chars", datetime.now(timezone.utc), [], None, "<special1>", "special.eml", attachments=attachments)
        mock_parse.return_value = mock_mail

        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        converter.convert()

        self.assertTrue((self.output_path / filename).exists(), "File with special characters should be saved correctly.")

    @patch('eml_to_threads.mailparser.parse_from_file')
    def test_subject_only_threading(self, mock_parse):
        """Tests that emails with same subject but no threading headers are grouped."""
        mock1, path1 = self._create_mock_email("Important Announcement", datetime(2023, 1, 5, 10, 0, 0, tzinfo=timezone.utc), [], None, "<subj1>", "subj1.eml")
        mock2, path2 = self._create_mock_email("Important Announcement", datetime(2023, 1, 5, 11, 0, 0, tzinfo=timezone.utc), [], None, "<subj2>", "subj2.eml")
        
        mock_parse.side_effect = lambda fp: {str(path1): mock1, str(path2): mock2}.get(fp)

        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        result = converter.convert()

        self.assertEqual(result['threads_created'], 1, "Should form one thread based on subject.")

    @patch('eml_to_threads.mailparser.parse_from_file')
    def test_zero_byte_attachment(self, mock_parse):
        """Ensures a zero-byte attachment is skipped and does not cause an error."""
        attachments = [{'filename': 'empty.txt', 'payload': '', 'mail_content_type': 'text/plain'}]
        mock_mail, path = self._create_mock_email("Empty File", datetime.now(timezone.utc), [], None, "<empty1>", "empty.eml", attachments=attachments)
        mock_parse.return_value = mock_mail

        converter = EmlToThreadsConverter(self.input_path, self.output_path)
        result = converter.convert()

        self.assertEqual(result['successful_files'], 1)
        self.assertFalse((self.output_path / "empty.txt").exists(), "Zero-byte attachment should not be saved.")

if __name__ == '__main__':
    unittest.main()
