from django.test import SimpleTestCase

from communications.utils.email_threading import (
    clean_message_id,
    normalize_email_subject,
    subjects_match,
)


class EmailThreadingUtilsTest(SimpleTestCase):
    def test_normalize_strips_re_fwd(self):
        self.assertEqual(
            normalize_email_subject('Re: Fwd: Presupuesto marzo'),
            'presupuesto marzo',
        )

    def test_normalize_empty(self):
        self.assertEqual(normalize_email_subject(''), '')
        self.assertEqual(normalize_email_subject(None), '')

    def test_subjects_match_ignores_prefixes(self):
        self.assertTrue(subjects_match('Presupuesto', 'Re: Presupuesto'))
        self.assertFalse(subjects_match('Presupuesto', 'Consulta técnica'))

    def test_clean_message_id_brackets(self):
        self.assertEqual(
            clean_message_id('<abc@mail.test>'),
            'abc@mail.test',
        )
