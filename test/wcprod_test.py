# contents of conftest.py
import pytest
import sqlite3

PROJECT_NAME='test_production'
NUM_PHOTONS_PER_FILE=1000000

@pytest.fixture(scope='session')
def project():
    cfg=f'''
    project: {PROJECT_NAME}
    rmin: 0
    rmax: 200
    zmin: 0
    zmax: 400
    gap_space: 30
    gap_angle: 10
    num_photons: 100000000
    '''
    from wcprod import wcprod_project
    return wcprod_project(cfg)

@pytest.fixture(scope="session")
def db(tmp_path_factory):
    from wcprod import wcprod_db
    f = tmp_path_factory.mktemp("db") / "pytest.db"
    return wcprod_db(f)


@pytest.fixture(scope="session")
def files(tmp_path_factory):
    d  = tmp_path_factory.mktemp('db')
    f1 = d / "cacca1"
    f2 = d / "cacca2"
    f1.write_text('data1')
    f2.write_text('data2')

    return (f1,f2)

# Test project creation
def test_project_creation(db,project):

    db.register_project(project)

def test_list_projects(db):

    assert len(db.list_projects())==1

def test_get_project(db):

    project = db.get_project(PROJECT_NAME)

    assert len(project.positions)

def test_list_all_tables(db):

    assert len(db.list_all_tables()) == 8

def test_list_positions(db,project):

    assert len(db.list_positions(PROJECT_NAME)) == len(project.positions)

def test_list_directions(db,project):

    assert len(db.list_directions(PROJECT_NAME)) == len(project.directions)

def test_register_file(db,files):

    for i,f in enumerate(files):
        db.register_file(PROJECT_NAME,i,f,NUM_PHOTONS_PER_FILE)

    assert len(db.list_files(PROJECT_NAME)) == len(files)

def test_exist_file(db,files):

    for f in files:
        assert db.exist_file(PROJECT_NAME,f)

def test_exist_project(db):

    assert db.exist_project(PROJECT_NAME)

def test_exist_table(db):

    assert db.exist_table('project')

def test_table_count(db):

    assert db.table_count(PROJECT_NAME) == 2

def test_table_id(db,project):

    assert db.table_id(PROJECT_NAME,0) == 0

    assert db.table_id(PROJECT_NAME,len(project.configs)-1) == db.table_count(PROJECT_NAME)-1

