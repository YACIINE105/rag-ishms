import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from models.ProjectModel import ProjectModel
from models.ChunkModel import ChunkModel
from models.db_schems.rag_ishms.schemes import Project, DataChunk


@pytest.fixture
def database():
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.begin.return_value.__aenter__ = AsyncMock()
    session.begin.return_value.__aexit__ = AsyncMock(return_value=False)
    for name in ("execute", "refresh", "flush"):
        setattr(session, name, AsyncMock())
    return MagicMock(return_value=session), session


async def test_create_and_find_project(database):
    client, session = database
    model = await ProjectModel.create_instance(client)
    project = Project(project_id=5)
    assert await model.create_project(project) is project
    session.add.assert_called_once_with(project)
    session.refresh.assert_awaited_once_with(project)
    result = MagicMock()
    session.execute.return_value = result
    result.scalar_one_or_none.return_value = project
    assert await model.get_project_or_create_one(5) is project
    session.flush.assert_not_awaited()
    result.scalar_one_or_none.return_value = None
    created = await model.get_project_or_create_one(6)
    assert created.project_id == 6
    session.flush.assert_awaited_once()


@pytest.mark.parametrize("total,pages", [(0, 0), (10, 1), (11, 2)])
async def test_project_pagination(database, total, pages):
    client, session = database
    count, records = MagicMock(), MagicMock()
    count.scalar_one.return_value = total
    records.scalars.return_value.all.return_value = ["project"]
    session.execute.side_effect = [count, records]
    assert await ProjectModel(client).get_all_projects(page=2, page_size=10) == (["project"], pages)
    query = session.execute.call_args.args[0].compile().params
    assert sorted(query.values()) == [10, 10]


async def test_chunk_create_find_and_batch(database):
    client, session = database
    model = await ChunkModel.create_instance(client)
    chunk = DataChunk(chunk_id=1, chunk_text="text", chunk_metadata={"page": 0})
    assert await model.create_chunk(chunk) is chunk
    session.refresh.assert_awaited_once_with(chunk)
    result = MagicMock()
    session.execute.return_value = result
    result.scalar_one_or_none.return_value = chunk
    assert await model.get_chunk(1) is chunk
    chunks = [chunk, chunk, chunk]
    assert await model.insert_many_chunks(chunks, batch_size=2) == 3
    assert [call.args[0] for call in session.add_all.call_args_list] == [chunks[:2], chunks[2:]]
    assert chunk.chunk_metadata == {"page": 0}


async def test_chunk_filters_counts_and_deletion(database):
    client, session = database
    model = ChunkModel(client)
    result = MagicMock(rowcount=2)
    session.execute.return_value = result
    result.scalars.return_value.all.return_value = ["chunk"]
    assert await model.get_project_chunks(7, page_number=3, page_size=5) == ["chunk"]
    assert sorted(session.execute.call_args.args[0].compile().params.values()) == [5, 7, 10]
    result.scalar.return_value = True
    assert await model.has_chunks_for_asset(2) is True
    result.scalar.return_value = 8
    assert await model.get_all_chunks_count(7) == 8
    assert await model.delete_chunk_by_asset_id(2) == 2
    assert session.execute.call_args.args[0].compile().params == {"chunk_asset_id_1": 2}
    assert await model.delete_chunk_by_project_id(7) == 2
    assert session.execute.call_args.args[0].compile().params == {"chunk_project_id_1": 7}


def test_upload_validation_and_collision(tmp_path, monkeypatch, settings):
    from controllers.DataController import DataController
    module = importlib.import_module("controllers.DataController")
    controller = DataController()
    controller.app_settings = settings
    assert controller.validate_uploaded_file(SimpleNamespace(content_type="text/plain", size=20))[0]
    assert not controller.validate_uploaded_file(SimpleNamespace(content_type="video/mp4", size=20))[0]
    assert not controller.validate_uploaded_file(SimpleNamespace(content_type="text/plain", size=2**21))[0]
    monkeypatch.setattr(module.ProjectController, "get_project_path", lambda *a, **k: str(tmp_path))
    monkeypatch.setattr(controller, "generate_random_strings", MagicMock(side_effect=["first", "second"]))
    (tmp_path / "first_report.pdf").touch()
    path, name = controller.unique_file_path_generator(" report?.pdf ", "7")
    assert name == "second_report.pdf"
    assert path == str(tmp_path / name)


def test_project_and_vector_paths(tmp_path):
    from controllers.ProjectController import ProjectController
    controller = ProjectController()
    controller.files_dir = str(tmp_path / "files")
    controller.vector_DB_dir = str(tmp_path / "vectors")
    assert controller.get_project_path("7") == str(tmp_path / "files" / "7")
    assert controller.get_database_path("qdrant") == str(tmp_path / "vectors" / "qdrant")
    assert controller.get_database_path("qdrant") == str(tmp_path / "vectors" / "qdrant")
    assert len(controller.generate_random_strings(12)) == 12
