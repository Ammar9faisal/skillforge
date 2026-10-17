"""Single-process local task storage. Metadata commits use atomic replacement."""
import os
from pathlib import Path
import re
import shutil
import tempfile
from threading import RLock
from uuid import uuid4

import cv2
import numpy as np
from pydantic import ValidationError

from ..models import Checkpoint, Task, timestamp


class StorageError(RuntimeError):
    def __init__(self, message, status_code=500):
        super().__init__(message)
        self.status_code = status_code


class TaskStore:
    MAX_CHECKPOINTS = 24

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.lock = RLock()

    def _directory(self, task_id):
        if not re.fullmatch(r'[0-9a-f]{32}', task_id):
            raise StorageError('Task not found.', 404)
        path = self.root / task_id
        if path.is_symlink():
            raise StorageError('Task directory is invalid.')
        return path

    @staticmethod
    def _atomic(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
                temporary = Path(output.name)
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, path)
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)

    def _save(self, task):
        task.updated_at = timestamp()
        self._atomic(self._directory(task.id) / 'task.json', task.model_dump_json(indent=2).encode())

    def create(self, title):
        with self.lock:
            task = Task(title=title)
            self._save(task)
            return task

    def get(self, task_id):
        with self.lock:
            path = self._directory(task_id) / 'task.json'
            try:
                task = Task.model_validate_json(path.read_bytes())
            except FileNotFoundError as exc:
                raise StorageError('Task not found.', 404) from exc
            except (ValidationError, OSError) as exc:
                raise StorageError('Saved task could not be read. Check local task storage.') from exc
            if task.id != task_id:
                raise StorageError('Saved task ID does not match its directory.')
            return task

    def list(self):
        with self.lock:
            if not self.root.exists():
                return []
            tasks = [self.get(p.name) for p in self.root.iterdir()
                     if p.is_dir() and re.fullmatch(r'[0-9a-f]{32}', p.name)]
            return sorted(tasks, key=lambda task: task.updated_at, reverse=True)

    def rename(self, task_id, title):
        with self.lock:
            task = self.get(task_id)
            if task.title != title:
                task.tutorial = None
            task.title = title
            self._save(task)
            return task

    @staticmethod
    def _checkpoint(task, checkpoint_id):
        for checkpoint in task.checkpoints:
            if checkpoint.id == checkpoint_id:
                return checkpoint
        raise StorageError('Checkpoint not found.', 404)

    def _image_path(self, task_id, filename):
        if not re.fullmatch(r'checkpoint_[0-9a-f]{32}\.jpg', filename):
            raise StorageError('Invalid stored image name.')
        path = self._directory(task_id) / filename
        if path.is_symlink():
            raise StorageError('Invalid stored image path.')
        return path

    @staticmethod
    def validate_jpeg(jpeg):
        frame = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR) if jpeg else None
        if frame is None or frame.size == 0:
            raise StorageError('Camera image is invalid. Reconnect the camera and retake the checkpoint.', 503)

    def capture(self, task_id, jpeg, note='', checkpoint_id=None):
        with self.lock:
            task = self.get(task_id)
            previous = None
            if checkpoint_id:
                checkpoint = self._checkpoint(task, checkpoint_id)
                previous = self._image_path(task_id, checkpoint.reference_image)
            else:
                if len(task.checkpoints) >= self.MAX_CHECKPOINTS:
                    raise StorageError('This task has reached the limit of 24 checkpoints.', 409)
                checkpoint = Checkpoint(position=len(task.checkpoints) + 1, reference_image='')
                task.checkpoints.append(checkpoint)
            self.validate_jpeg(jpeg)
            checkpoint.reference_image = f'checkpoint_{uuid4().hex}.jpg'
            checkpoint.note = note
            task.tutorial = None
            checkpoint.created_at = timestamp()
            image_path = self._image_path(task_id, checkpoint.reference_image)
            self._atomic(image_path, jpeg)
            try:
                self._save(task)
            except Exception:
                image_path.unlink(missing_ok=True)
                raise
            if previous:
                previous.unlink(missing_ok=True)
            return task

    def update_note(self, task_id, checkpoint_id, note):
        with self.lock:
            task = self.get(task_id)
            checkpoint = self._checkpoint(task, checkpoint_id)
            if checkpoint.note != note:
                task.tutorial = None
            checkpoint.note = note
            self._save(task)
            return task

    def delete_checkpoint(self, task_id, checkpoint_id):
        with self.lock:
            task = self.get(task_id)
            checkpoint = self._checkpoint(task, checkpoint_id)
            image = self._image_path(task_id, checkpoint.reference_image)
            task.checkpoints.remove(checkpoint)
            task.tutorial = None
            for position, remaining in enumerate(task.checkpoints, 1):
                remaining.position = position
            self._save(task)
            image.unlink(missing_ok=True)
            return task

    def image(self, task_id, checkpoint_id):
        with self.lock:
            task = self.get(task_id)
            checkpoint = self._checkpoint(task, checkpoint_id)
            try:
                jpeg = self._image_path(task_id, checkpoint.reference_image).read_bytes()
            except FileNotFoundError as exc:
                raise StorageError('Reference image is missing. Retake this checkpoint.', 404) from exc
            self.validate_jpeg(jpeg)
            return jpeg

    def delete(self, task_id):
        with self.lock:
            self.get(task_id)
            shutil.rmtree(self._directory(task_id))

    def generation_snapshot(self, task_id):
        with self.lock:
            task = self.get(task_id)
            if len(task.checkpoints) < 2:
                raise StorageError('Capture at least two checkpoints before generating a tutorial.', 409)
            images = []
            for checkpoint in task.checkpoints:
                try:
                    images.append(self.image(task_id, checkpoint.id))
                except StorageError as exc:
                    raise StorageError(f'Reference image for checkpoint {checkpoint.position} is missing or invalid. Retake it before generation.', 409) from exc
            if sum(len(image) for image in images) > 12 * 1024 * 1024:
                raise StorageError('Reference images exceed the generation limit. Use fewer checkpoints or a lower camera resolution.', 413)
            return task, images

    def save_tutorial(self, task_id, tutorial, expected_updated_at):
        with self.lock:
            task = self.get(task_id)
            if task.updated_at != expected_updated_at:
                raise StorageError('The task changed during generation. Refresh and generate again using the updated checkpoints.', 409)
            tutorial.validate_checkpoints(task.checkpoints)
            task.tutorial = tutorial
            self._save(task)
            return task
