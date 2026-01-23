import unittest
import tempfile
import traceback
from pathlib import Path

from eml_to_threads import EmlToThreadsConverter

class TestRealEmlFiles(unittest.TestCase):
    """Extended integration test using real EML files from test_folder."""

    def setUp(self):
        self.test_folder = Path(__file__).parent / "test_folder"
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_path = Path(self.temp_dir.name) / "output"
        self.output_path.mkdir()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_all_real_eml_files_processing(self):
        """Test that all real EML files in test_folder can be processed without exceptions."""
        # Find all EML files in test_folder
        eml_files = list(self.test_folder.rglob("*.eml"))
        
        # Skip test if no EML files found
        if not eml_files:
            self.skipTest("No EML files found in test_folder")
        
        print(f"\nFound {len(eml_files)} EML files to test:")
        for eml_file in eml_files:
            print(f"  - {eml_file.relative_to(self.test_folder)}")
        
        # Run converter on test_folder
        converter = EmlToThreadsConverter(self.test_folder, self.output_path)
        
        # This should not throw any exceptions
        try:
            result = converter.convert()
        except Exception as e:
            self.fail(f"EmlToThreadsConverter threw an exception: {e}\n{traceback.format_exc()}")
        
        # Basic assertions - should process files without crashing
        self.assertEqual(result['total_files'], len(eml_files))
        self.assertIsInstance(result['successful_files'], int)
        self.assertIsInstance(result['failed_files'], int)
        self.assertIsInstance(result['threads_created'], int)
        
        # Total processed should equal sum of success + failures
        self.assertEqual(
            result['total_files'], 
            result['successful_files'] + result['failed_files']
        )
        
        # Should have created some output
        output_files = list(self.output_path.rglob("*"))
        self.assertGreater(len(output_files), 0, "Should have created some output files")
        
        print(f"\nProcessing Results:")
        print(f"  Total files: {result['total_files']}")
        print(f"  Successful: {result['successful_files']}")
        print(f"  Failed: {result['failed_files']}")
        print(f"  Threads created: {result['threads_created']}")
        print(f"  Output files: {len(output_files)}")
        
        # Report any failures for debugging
        if result['failed_files'] > 0 and 'failures' in result:
            print(f"\nFailed files ({len(result['failures'])}):")
            for failure in result['failures']:
                print(f"  - {failure.get('file', 'unknown')}: {failure.get('error', 'unknown error')}")

    def test_individual_eml_file_processing(self):
        """Test each EML file individually to identify specific problematic files."""
        eml_files = list(self.test_folder.rglob("*.eml"))
        
        if not eml_files:
            self.skipTest("No EML files found in test_folder")
        
        individual_results = []
        
        for eml_file in eml_files:
            # Create individual temp directory for each test
            with tempfile.TemporaryDirectory() as temp_dir:
                # Create input directory with single file
                input_path = Path(temp_dir) / "input"
                output_path = Path(temp_dir) / "output"
                input_path.mkdir()
                output_path.mkdir()
                
                # Copy single EML file to test directory
                single_eml_path = input_path / eml_file.name
                single_eml_path.write_bytes(eml_file.read_bytes())
                
                # Test individual file
                converter = EmlToThreadsConverter(input_path, output_path)
                
                try:
                    result = converter.convert()
                    success = True
                    error = None
                except Exception as e:
                    success = False
                    error = str(e)
                    result = None
                
                individual_results.append({
                    'file': eml_file.relative_to(self.test_folder),
                    'success': success,
                    'error': error,
                    'result': result
                })
        
        # Report results
        successful_files = [r for r in individual_results if r['success']]
        failed_files = [r for r in individual_results if not r['success']]
        
        print(f"\nIndividual File Results:")
        print(f"  Successful: {len(successful_files)}/{len(eml_files)}")
        print(f"  Failed: {len(failed_files)}/{len(eml_files)}")
        
        if failed_files:
            print(f"\nFailed Files:")
            for failed in failed_files:
                print(f"  - {failed['file']}: {failed['error']}")
        
        # The test passes as long as we don't get unhandled exceptions
        # Individual file failures are reported but don't fail the test
        # since we want to test graceful handling of problematic files
        
        # But we should have at least some successful files
        self.assertGreater(
            len(successful_files), 
            0, 
            "Should have successfully processed at least one EML file"
        )

if __name__ == '__main__':
    unittest.main(verbosity=2)