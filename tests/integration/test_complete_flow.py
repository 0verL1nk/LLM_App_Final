"""
Integration test for complete user flow.
"""

import pytest
import tempfile
import os
from unittest.mock import MagicMock, patch

from src.llm_app.core.database import DatabaseManager
from src.llm_app.core.auth import AuthManager
from src.llm_app.core.file_handler import FileHandler
from src.llm_app.core.text_processor import TextProcessor
from src.llm_app.api.llm_client import LLMClient


class TestCompleteUserFlow:
    """Integration tests for complete user workflow."""

    def test_user_registration_to_file_upload(self, temp_db, sample_user_data):
        """Test complete flow from user registration to file upload."""
        # Initialize components
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        auth = AuthManager(db_manager=db)
        file_handler = FileHandler(db_manager=db)

        # Step 1: Register user
        success, token, error = auth.register(
            sample_user_data['username'],
            sample_user_data['password']
        )
        assert success is True
        assert token is not None

        # Step 2: Login
        success, token, error = auth.login(
            sample_user_data['username'],
            sample_user_data['password']
        )
        assert success is True
        assert token is not None

        # Step 3: Get UUID
        uuid = auth.get_uuid_by_token(token)
        assert uuid is not None

        # Step 4: Save API key
        db.update_user_api_key(uuid, sample_user_data['api_key'])
        saved_api_key = db.get_user_api_key(uuid)
        assert saved_api_key == sample_user_data['api_key']

        # Step 5: Upload file
        mock_file = MagicMock()
        mock_file.name = 'test.pdf'
        mock_file.read.side_effect = [b'file content', b'']

        with tempfile.TemporaryDirectory() as tmpdir:
            success, message, file_info = file_handler.process_uploaded_file(
                mock_file,
                uuid
            )
            assert success is True
            assert 'file_path' in file_info

        # Step 6: Verify file is in database
        files = db.get_user_files(uuid)
        assert len(files) == 1

    def test_file_processing_workflow(self, temp_db, sample_user_data, sample_text_content):
        """Test complete file processing workflow."""
        # Initialize components
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        auth = AuthManager(db_manager=db)
        file_handler = FileHandler(db_manager=db)
        text_processor = TextProcessor(db_manager=db, file_handler=file_handler)

        # Setup user
        auth.register(sample_user_data['username'], sample_user_data['password'])
        uuid = auth.get_uuid_by_token(auth.register('user', 'pass')[1])

        # Save API key and set up LLM client
        db.update_user_api_key(uuid, sample_user_data['api_key'])
        llm_client = MagicMock(spec=LLMClient)
        text_processor.set_llm_client(llm_client)

        # Mock LLM responses
        llm_client.chat_completion.return_value = '{"研究背景": ["text"]}'

        # Create test file
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdf', delete=False) as f:
            f.write(b'Test file content')
            file_path = f.name

        try:
            # Extract text
            success, extracted_text = text_processor.extract_text(file_path)
            assert success is True

            # Process text extraction
            success, message, content = text_processor.text_extraction(
                file_path,
                'test-uid'
            )
            assert success is True

            # Verify content is saved
            saved_content = db.get_content_by_uid('test-uid', 'file_extraction')
            assert saved_content is not None

        finally:
            # Cleanup
            os.unlink(file_path)

    def test_user_session_management(self, temp_db, sample_user_data):
        """Test user session management."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        auth = AuthManager(db_manager=db)

        # Register user
        success, token1, _ = auth.register(
            sample_user_data['username'],
            sample_user_data['password']
        )
        assert success is True

        # Login
        success, token2, _ = auth.login(
            sample_user_data['username'],
            sample_user_data['password']
        )
        assert success is True

        # Get UUID by token
        uuid = auth.get_uuid_by_token(token2)
        assert uuid is not None

        # Check token validity
        assert auth.is_token_valid(token2) is True
        assert not auth.is_token_expired(token2)

        # Verify user can perform actions
        db.update_user_api_key(uuid, 'api_key')
        assert db.get_user_api_key(uuid) == 'api_key'

    def test_file_deduplication(self, temp_db, sample_user_data):
        """Test file deduplication logic."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        file_handler = FileHandler(db_manager=db)

        uuid = 'user-uuid'

        # Create mock file
        mock_file = MagicMock()
        mock_file.name = 'document.pdf'
        mock_file.read.side_effect = [b'identical content', b'', b'identical content', b'']

        with tempfile.TemporaryDirectory() as tmpdir:
            # Upload same file twice
            result1 = file_handler.save_uploaded_file(mock_file, uuid, tmpdir)
            mock_file.seek(0)
            result2 = file_handler.save_uploaded_file(mock_file, uuid, tmpdir)

            # Should have same UID
            assert result1['uid'] == result2['uid']

            # Should have only one file in database
            files = file_handler.get_user_files(uuid)
            assert len(files) == 1

    def test_content_persistence(self, temp_db):
        """Test that content persists across sessions."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()

        uid = 'test-uid'
        content_data = {
            '研究背景': ['背景信息'],
            '研究目的': ['研究目标']
        }

        # Save content
        import json
        db.save_content_to_database(
            uid,
            '/tmp/test.txt',
            json.dumps(content_data),
            'file_extraction'
        )

        # Retrieve content (simulating new session)
        db2 = DatabaseManager(db_path=temp_db)
        saved_content = db2.get_content_by_uid(uid, 'file_extraction')

        assert saved_content is not None
        parsed = json.loads(saved_content)
        assert parsed == content_data

    def test_api_key_isolation(self, temp_db):
        """Test that API keys are properly isolated per user."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()

        # Create two users
        users = [
            ('user1', 'pass1', 'key1'),
            ('user2', 'pass2', 'key2')
        ]

        # Save API keys
        for username, password, api_key in users:
            auth = AuthManager(db_manager=db)
            auth.register(username, password)
            uuid = auth.get_uuid_by_token(auth.register(username, password)[1])
            db.update_user_api_key(uuid, api_key)

        # Verify each user gets their own key
        for username, _, api_key in users:
            auth = AuthManager(db_manager=db)
            uuid = auth.get_uuid_by_token(auth.register(username, 'pass')[1])
            saved_key = db.get_user_api_key(uuid)
            assert saved_key == api_key

    def test_task_status_tracking(self, temp_db):
        """Test that task statuses are properly tracked."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()

        from src.llm_app.queue.task_queue import TaskQueueManager, TaskStatus

        task_manager = TaskQueueManager()
        task_manager.init_task_table()

        # Create task
        task_id = 'task-123'
        uid = 'file-uid'
        task_manager.create_task(task_id, uid, 'file_extraction')

        # Check task status
        status = task_manager.get_task_status(task_id)
        assert status is not None
        assert status['status'] == TaskStatus.PENDING.value

        # Update status
        task_manager.update_task_status(task_id, TaskStatus.STARTED)
        updated_status = task_manager.get_task_status(task_id)
        assert updated_status['status'] == TaskStatus.STARTED.value

    def test_error_handling_in_workflow(self, temp_db, sample_user_data):
        """Test error handling in the complete workflow."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        auth = AuthManager(db_manager=db)

        # Try to login non-existent user
        success, token, error = auth.login('nonexistent', 'password')
        assert success is False
        assert '错误' in error

        # Register user
        auth.register(sample_user_data['username'], sample_user_data['password'])
        uuid = auth.get_uuid_by_token(auth.register('user', 'pass')[1])

        # Try to get API key for non-existent user
        non_existent_key = db.get_user_api_key('non-existent-uuid')
        assert non_existent_key is None

        # Verify existing user still works
        db.update_user_api_key(uuid, 'valid_key')
        assert db.get_user_api_key(uuid) == 'valid_key'

    def test_concurrent_user_sessions(self, temp_db):
        """Test handling multiple concurrent user sessions."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()

        # Create multiple users
        users = []
        for i in range(5):
            username = f'user{i}'
            password = f'pass{i}'
            auth = AuthManager(db_manager=db)
            success, token, _ = auth.register(username, password)
            assert success is True
            uuid = auth.get_uuid_by_token(token)
            users.append((username, password, uuid))

        # Verify each user can authenticate
        for username, password, uuid in users:
            auth = AuthManager(db_manager=db)
            success, token, _ = auth.login(username, password)
            assert success is True
            retrieved_uuid = auth.get_uuid_by_token(token)
            assert retrieved_uuid == uuid

            # Each user has unique API key
            db.update_user_api_key(uuid, f'key-{username}')
            assert db.get_user_api_key(uuid) == f'key-{username}'