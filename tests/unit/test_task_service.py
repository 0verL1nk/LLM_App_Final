"""
Unit tests for TaskService.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import sys

sys.path.insert(0, "/home/ling/LLM_App_Final/src")

from llm_app.services.task_service import TaskService


class TestTaskService:
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.fixture
    def task_service(self, mock_db):
        return TaskService(mock_db)

    @pytest.fixture
    def sample_file(self):
        file = MagicMock()
        file.id = "file-123"
        file.user_uuid = "user-uuid-123"
        file.original_filename = "test.pdf"
        return file

    @pytest.fixture
    def sample_task(self):
        task = MagicMock()
        task.task_id = "task-123"
        task.task_type = "extract"
        task.user_uuid = "user-uuid-123"
        task.file_id = "file-123"
        task.status = "pending"
        task.progress = 0
        task.result = None
        task.error_message = None
        task.created_at = datetime.utcnow()
        task.updated_at = datetime.utcnow()
        task.completed_at = None
        task.started_at = None
        task.job_id = None
        return task

    def setup_db_return(self, mock_db, return_value):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = return_value
        mock_result.scalar.return_value = 10
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [return_value] if return_value else []
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute = AsyncMock(return_value=mock_result)

    @pytest.mark.asyncio
    async def test_create_task_success(self, task_service, mock_db, sample_file):
        self.setup_db_return(mock_db, sample_file)

        task = await task_service.create_task(
            user_uuid="user-uuid-123",
            file_id="file-123",
            task_type="extract",
            options={"format": "text"},
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        added_task = mock_db.add.call_args[0][0]
        assert added_task.task_type == "extract"
        assert added_task.user_uuid == "user-uuid-123"

    @pytest.mark.asyncio
    async def test_create_task_file_not_found(self, task_service, mock_db):
        self.setup_db_return(mock_db, None)

        with pytest.raises(ValueError, match="File not found"):
            await task_service.create_task(
                user_uuid="user-uuid-123",
                file_id="nonexistent-file",
                task_type="extract",
            )

        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_task_with_options(self, task_service, mock_db, sample_file):
        self.setup_db_return(mock_db, sample_file)

        options = {"summary_type": "brief", "max_length": 500}
        await task_service.create_task(
            user_uuid="user-uuid-123",
            file_id="file-123",
            task_type="summarize",
            options=options,
        )

        added_task = mock_db.add.call_args[0][0]
        assert added_task.result == {"options": options}

    @pytest.mark.asyncio
    async def test_create_task_different_types(
        self, task_service, mock_db, sample_file
    ):
        self.setup_db_return(mock_db, sample_file)

        task_types = ["extract", "summarize", "qa", "rewrite", "mindmap"]
        for task_type in task_types:
            mock_db.add.reset_mock()
            await task_service.create_task(
                user_uuid="user-uuid-123",
                file_id="file-123",
                task_type=task_type,
            )
            added_task = mock_db.add.call_args[0][0]
            assert added_task.task_type == task_type

    @pytest.mark.asyncio
    async def test_get_task_success(self, task_service, mock_db, sample_task):
        self.setup_db_return(mock_db, sample_task)

        task = await task_service.get_task("task-123", "user-uuid-123")

        assert task == sample_task
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_task_not_found(self, task_service, mock_db):
        self.setup_db_return(mock_db, None)

        task = await task_service.get_task("nonexistent", "user-uuid-123")
        assert task is None

    @pytest.mark.asyncio
    async def test_get_task_status_success(self, task_service, mock_db, sample_task):
        self.setup_db_return(mock_db, sample_task)

        status = await task_service.get_task_status("task-123", "user-uuid-123")

        assert status is not None
        assert status["task_id"] == "task-123"
        assert status["task_type"] == "extract"
        assert status["status"] == "pending"

    @pytest.mark.asyncio
    async def test_get_task_status_not_found(self, task_service, mock_db):
        self.setup_db_return(mock_db, None)

        status = await task_service.get_task_status("nonexistent", "user-uuid-123")
        assert status is None

    @pytest.mark.asyncio
    async def test_update_task_status_processing(
        self, task_service, mock_db, sample_task
    ):
        sample_task.started_at = None
        self.setup_db_return(mock_db, sample_task)

        await task_service.update_task_status("task-123", status="processing")

        assert sample_task.status == "processing"
        assert sample_task.started_at is not None
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_task_status_completed(
        self, task_service, mock_db, sample_task
    ):
        sample_task.started_at = datetime.utcnow()
        self.setup_db_return(mock_db, sample_task)

        await task_service.update_task_status(
            "task-123",
            status="completed",
            progress=100,
            result={"text": "extracted content"},
        )

        assert sample_task.status == "completed"
        assert sample_task.progress == 100
        assert sample_task.completed_at is not None

    @pytest.mark.asyncio
    async def test_update_task_status_failed(self, task_service, mock_db, sample_task):
        self.setup_db_return(mock_db, sample_task)

        await task_service.update_task_status(
            "task-123",
            status="failed",
            error_message="Processing failed: file corrupt",
        )

        assert sample_task.status == "failed"
        assert sample_task.error_message == "Processing failed: file corrupt"

    @pytest.mark.asyncio
    async def test_update_task_progress_bounds(
        self, task_service, mock_db, sample_task
    ):
        self.setup_db_return(mock_db, sample_task)

        await task_service.update_task_status("task-123", progress=150)
        assert sample_task.progress == 100

        await task_service.update_task_status("task-123", progress=-10)
        assert sample_task.progress == 0

    @pytest.mark.asyncio
    async def test_update_task_result_merges(self, task_service, mock_db, sample_task):
        sample_task.result = {"options": {"type": "brief"}}
        self.setup_db_return(mock_db, sample_task)

        await task_service.update_task_status(
            "task-123",
            result={"text": "new content"},
        )

        assert sample_task.result == {
            "options": {"type": "brief"},
            "text": "new content",
        }

    @pytest.mark.asyncio
    async def test_update_task_not_found(self, task_service, mock_db):
        self.setup_db_return(mock_db, None)

        result = await task_service.update_task_status(
            "nonexistent", status="completed"
        )
        assert result is None
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_tasks_success(self, task_service, mock_db, sample_task):
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 25

        mock_list_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [sample_task]
        mock_list_result.scalars.return_value = mock_scalars

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_list_result])

        tasks, total = await task_service.list_tasks(
            user_uuid="user-uuid-123",
            page=1,
            page_size=20,
        )

        assert total == 25
        assert len(tasks) == 1

    @pytest.mark.asyncio
    async def test_list_tasks_with_status_filter(
        self, task_service, mock_db, sample_task
    ):
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 5

        mock_list_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [sample_task]
        mock_list_result.scalars.return_value = mock_scalars

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_list_result])

        tasks, total = await task_service.list_tasks(
            user_uuid="user-uuid-123",
            status="completed",
        )

        assert total == 5

    @pytest.mark.asyncio
    async def test_list_tasks_with_type_filter(
        self, task_service, mock_db, sample_task
    ):
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 3

        mock_list_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [sample_task]
        mock_list_result.scalars.return_value = mock_scalars

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_list_result])

        tasks, total = await task_service.list_tasks(
            user_uuid="user-uuid-123",
            task_type="extract",
        )

        assert total == 3

    @pytest.mark.asyncio
    async def test_cancel_task_success(self, task_service, mock_db, sample_task):
        sample_task.status = "pending"
        self.setup_db_return(mock_db, sample_task)

        result = await task_service.cancel_task("task-123", "user-uuid-123")

        assert result is True
        assert sample_task.status == "cancelled"
        assert sample_task.completed_at is not None
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_task_processing(self, task_service, mock_db, sample_task):
        sample_task.status = "processing"
        self.setup_db_return(mock_db, sample_task)

        result = await task_service.cancel_task("task-123", "user-uuid-123")

        assert result is True
        assert sample_task.status == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_task_already_completed(
        self, task_service, mock_db, sample_task
    ):
        sample_task.status = "completed"
        self.setup_db_return(mock_db, sample_task)

        result = await task_service.cancel_task("task-123", "user-uuid-123")

        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_task_already_failed(self, task_service, mock_db, sample_task):
        sample_task.status = "failed"
        self.setup_db_return(mock_db, sample_task)

        result = await task_service.cancel_task("task-123", "user-uuid-123")

        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_task_not_found(self, task_service, mock_db):
        self.setup_db_return(mock_db, None)

        result = await task_service.cancel_task("nonexistent", "user-uuid-123")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_existing_extraction_found(
        self, task_service, mock_db, sample_task
    ):
        sample_task.task_type = "extract"
        sample_task.status = "completed"
        self.setup_db_return(mock_db, sample_task)

        task = await task_service.get_existing_extraction("file-123", "user-uuid-123")

        assert task == sample_task

    @pytest.mark.asyncio
    async def test_get_existing_extraction_not_found(self, task_service, mock_db):
        self.setup_db_return(mock_db, None)

        task = await task_service.get_existing_extraction("file-123", "user-uuid-123")

        assert task is None
