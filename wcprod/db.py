import sqlite3, time, os
import pandas as pd
from contextlib import closing
import numpy as np
from tqdm import tqdm
import datetime
from .project import wcprod_project

class TableNotFoundError(Exception):
    pass
class ProjectNotFoundError(Exception):
    pass
class ProjectIntegrityError(Exception):
    pass

class wcprod_db:
    
    def __init__(self,dbname:str):
        """Constructor

        Constructs API instance for WC production database.
        Creates the database with the name being the given argument dbname.

        Parameters
        ----------
        dbname : str
            Name of the database to connect or create if it does not exist
        """
        self._conn = sqlite3.connect(dbname)
        with closing(self._conn.cursor()) as cur:
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='project'")
            result = cur.fetchall()
            if len(result) < 1:
                cmd  = "CREATE TABLE project "
                cmd += " (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, rmin FLOAT, rmax FLOAT, zmin FLOAT, zmax FLOAT,"
                cmd += " gap_space FLOAT, gap_angle FLOAT, n_phi_start INT, num_config INT, num_tables INT, num_photons INT)"
                cur.execute(cmd)
    
    def check_integrity(self,project:str):
        """Test function for the database integrity

        Runs integrity checks for a project performing read-only access to the database.
        The function can be used to check the minimal validity of a project.
        The function is run also within the register_project() function.

        Parameters
        ----------
        project : str
            Name of the project to check the integrity
        """
        with closing(self._conn.cursor()) as cur:
            if not self.exist_table("project"):
                raise TableNotFoundError("The 'project' table not found (this may not be the database for wcprod_db)")
            # - project exists in the project table
            cmd = f"SELECT rmin, rmax, zmin, zmax, gap_space, gap_angle, n_phi_start, num_config, num_tables, num_photons FROM project WHERE name = '{project}'"
            cur.execute(cmd)
            res = cur.fetchall()
            if len(res) < 1:
                raise ProjectNotFoundError(f"Project '{project}' not found in the project table")
            if len(res) > 1:
                raise ProjectIntegrityError(f"Found more than 1 entry with the name '{project}' in the project table")
            rmin,rmax,zmin,zmax,gap_space,gap_angle,n_phi_start,num_config,num_tables,num_photons = res[0]
            # - geo table
            if not self.exist_table(f"geo_{project}"):
                raise ProjectIntegrityError(f"Geometry table not found for the project '{project}'")
            cmd = f"SELECT COUNT(*) FROM geo_{project} WHERE geo_type=0"
            cur.execute(cmd)
            pos_id_ctr = cur.fetchall()[0][0]
            cmd = f"SELECT COUNT(*) FROM geo_{project} WHERE geo_type=1"
            cur.execute(cmd)
            dir_id_ctr = cur.fetchall()[0][0]
            cmd = f"SELECT COUNT(*) FROM geo_{project} WHERE geo_type=2"
            cur.execute(cmd)
            vox_id_ctr = cur.fetchall()[0][0]
            cmd = f"SELECT COUNT(*) FROM geo_{project} WHERE geo_type>2"
            cur.execute(cmd)
            zero_ctr = cur.fetchall()[0][0]            
            if not zero_ctr == 0:
                raise ProjectIntegrityError(f"Found unexpected geo_type values (must be 0 or 1)")
            if not vox_id_ctr == num_config:
                raise ProjectIntegrityError(f"Voxel ID counters ({vox_id_ctr} is inconsistent with the config count {num_config}")
            if not (pos_id_ctr * dir_id_ctr) == num_config:
                raise ProjectIntegrityError(f"Position and direction ID counters ({pos_id_ctr} and {dir_id_ctr}) are inconsistent with the config count {num_config}")
            # - map table
            if not self.exist_table(f"map_{project}"):
                raise ProjectIntegrityError(f"Config mapping table not found for the project '{project}'")
            cmd = f"SELECT table_id, config_range_min, config_range_max, photon_ctr, target_ctr FROM map_{project}"
            cur.execute(cmd)
            data_map = np.array(cur.fetchall())
            if not (len(data_map[:,0]) == len(np.unique(data_map[:,0])) == (data_map[:,0].max()+1)):
                raise ProjectIntegrityError(f"Duplicate or lacking table_id in map_{project} table")
            if not len(data_map[:,0]) == num_tables:
                raise ProjectIntegrityError(f"The number of table {num_tables} is inconsistent with the number of unique table_id values {len(data_map[:,0])}")
            nph_per_table = data_map[:,4] == (data_map[:,2]-data_map[:,1]+1)*num_photons
            if not nph_per_table.sum() == len(data_map[:,0]):
                raise ProjectIntegrityError(f"Mismatch for the expected number of photons found in the table_ids: {np.where(nph_per_table == False)[0]}")
            for i in range(len(data_map)):
                cfgmin,cfgmax = data_map[i,1:3]
                if not cfgmin < cfgmax:
                    raise ProjectIntegrityError(f"Configuration range {cfgmin} => {cfgmax} is invalid (table {data_map[i,0]} in map_{project})")
                if (i+1) < len(data_map) and cfgmax >= data_map[i+1,1]:
                    raise ProjectIntegrityError(f"Configuration should not overlap: table {data_map[i,0]} range {cfgmin}=>{cfgmax} but the next table starts at {data_map[i+1,1]}")
            # - cfg table tqdm
            for index in tqdm(data_map[:,0]):
                if not self.exist_table(f"cfg_{project}{index}"):
                    raise ProjectIntegrityError(f"Configuration table cfg_{project}{index} should but does not exist.")
                cmd = f"SELECT MIN(config_id), MAX(config_id), MAX(pos_id), MAX(dir_id) FROM cfg_{project}{index}"
                cur.execute(cmd)
                cfg_min, cfg_max, pos_max, dir_max = cur.fetchall()[0]
                if cfg_min < data_map[index,1] or data_map[index,2] < cfg_max:
                    raise ProjectIntegrityError(f"Configuration table cfg_{project}{index} has invalid config_id range {cfg_min}=>{cfg_max} (expected: {data_map[index,1:3]})")
                if pos_id_ctr <= pos_max:
                    raise ProjectIntegrityError(f"Configuration table cfg_{project}{index} has unexpected maximum pos_id value {pos_max} (should be < {pos_id_ctr})")
                if dir_id_ctr <= dir_max:
                    raise ProjectIntegrityError(f"Configuration table cfg_{project}{index} has unexpected maximum dir_id value {dir_max} (should be < {dir_id_ctr})")
                if n_phi_start == 0:
                    cmd = f"SELECT MIN(ABS(x)), MAX(ABS(x)), MIN(ABS(y)), MAX(ABS(y)), MIN(z), MAX(z), MIN(theta), MAX(theta), MIN(phi), MAX(phi) FROM cfg_{project}{index}"
                    cur.execute(cmd)
                    xmin, xmax, ymin, ymax, zmin2, zmax2, tmin, tmax, pmin, pmax = cur.fetchall()[0]
                    if xmin < rmin or rmax < xmax:
                        raise ProjectIntegrityError(f"Configuration table cfg_{project}{index} has unexpected abs(x) value range {xmin}=>{xmax} (expected {rmin}=>{rmax})")
                    if ymin < rmin or rmax < ymax:
                        raise ProjectIntegrityError(f"Configuration table cfg_{project}{index} has unexpected abs(y) value range {ymin}=>{ymax} (expected {rmin}=>{rmax})")
                    if zmin2 < zmin or zmax < zmax2:
                        raise ProjectIntegrityError(f"Configuration table cfg_{project}{index} has unexpected z value range {zmin2}=>{zmax2} (expected {zmin}=>{zmax})")
                    if tmin < 0 or 180 < tmax:
                        raise ProjectIntegrityError(f"Configuration table cfg_{project}{index} has unexpected theta value range {tmin}=>{tmax} (expected 0=>180)")
                    if pmin < 0 or 360 < pmax:
                        raise ProjectIntegrityError(f"Configuration table cfg_{project}{index} has unexpected phi value range {pmin}=>{pmax} (expected 0=>360)")
                else:
                    cmd = f"SELECT MIN(r0), MAX(r0), MIN(r1), MAX(r1), MIN(phi0), MAX(phi0), MIN(phi1), MAX(phi1), MIN(z0), MAX(z0), MIN(z1), MAX(z1) FROM cfg_{project}{index}"
                    cur.execute(cmd)
                    r0min, r0max, r1min, r1max, phi0min, phi0max, phi1min, phi1max, z0min, z0max, z1min, z1max = cur.fetchall()[0]
                    if r0min < rmin or rmax < r0max:
                        raise ProjectIntegrityError(f"Configuration table cfg_{project}{index} has unexpected r0 value range {r0min}=>{r0max} (expected {rmin}=>{rmax})")
                    if r1min < rmin or rmax < r1max:
                        raise ProjectIntegrityError(f"Configuration table cfg_{project}{index} has unexpected r1 value range {r1min}=>{r1max} (expected {rmin}=>{rmax})")
                    if phi0min < 0 or 360 < phi0max:
                        raise ProjectIntegrityError(f"Configuration table cfg_{project}{index} has unexpected phi0 value range {phi0min}=>{phi0max} (expected 0=>360)")
                    if phi1min < 0 or 360 < phi1max:
                        raise ProjectIntegrityError(f"Configuration table cfg_{project}{index} has unexpected phi1 value range {phi1min}=>{phi1max} (expected 0=>360)")
                    if z0min < zmin or zmax < z0max:
                        raise ProjectIntegrityError(f"Configuration table cfg_{project}{index} has unexpected z0 value range {z0min}=>{z0max} (expected {zmin}=>{zmax})")
                    if z1min < zmin or zmax < z1max:
                        raise ProjectIntegrityError(f"Configuration table cfg_{project}{index} has unexpected z1 value range {z1min}=>{z1max} (expected {zmin}=>{zmax})")
                    
                
                # - file table
                cmd = f"SELECT MIN(config_id),MAX(config_id) FROM file_{project}{index}"
                cur.execute(cmd)
                res = cur.fetchall()
                if res[0][0] is not None and (res[0][0] < cfg_min or cfg_max < res[0][1]):
                    raise ProjectIntegrityError(f"File table file_{project}{index} contains unexpected config_id range {res[0][0]}=>{res[0][1]} (expected {cfg_min}=>{cfg_max})")

    
    def list_all_tables(self):
        """List all tables in the database

        Returns
        -------
        list
            List of tables (string values) in the database
        """
        cmd = "SELECT name from sqlite_master WHERE type='table'"
        with closing(self._conn.cursor()) as cur:
            cur.execute(cmd)
            res=[ts[0] for ts in cur.fetchall()]
            return res


    def list_projects(self):
        """List all projects in the database

        Returns
        -------
        list
            List of projects (string values) in the database
        """
        with closing(self._conn.cursor()) as cur:
            cur.execute("SELECT name FROM project")
            #result = cur.fetchall()
            return [res[0] for res in cur.fetchall()]



    def get_project(self,project:str):
        """Retrieve project information from the database

        Creates wcprod_project instance filled with information from the database

        Parameters
        ----------
        project : str
            The name of a project to access in the database

        Returns
        -------
        wcprod_project
            Instance filled with information from the database
        """  
        with closing(self._conn.cursor()) as cur:

            p=wcprod_project()

            cur.execute(f"SELECT zmin,zmax,rmin,rmax,gap_space,gap_angle,n_phi_start,num_photons FROM project WHERE name='{project}' LIMIT 1")
            res=cur.fetchall()
            if len(res)<1:
                return None
            res=res[0]
            p._project = project
            p._zmin, p._zmax, p._rmin, p._rmax = res[0:4]
            p._gap_space, p._gap_angle, p._n_phi_start, p._num_photons = res[4:]

            p._positions  = self.list_positions(project)[:,0:3]
            p._directions = self.list_directions(project)[:,0:2]
            p._voxels = self.list_voxels(project)[:,0:6]

            from wcprod.utils import coordinates, volumes
            if p._n_phi_start == 0:
                p._configs = coordinates(p.positions,p.directions)
            else:
                p._configs = volumes(p.voxels)

            return p
    

    def get_config(self,project:str,config_id:int):
        """Retrieve a job configuration from the database

        Retrieve a job configuration (x,y,z,theta,phi) and production info (file and photon count produced so far).

        Parameters
        ----------
        project : str
            The name of a project to access in the database

        Returns
        -------
        dict
            Contains (x,y,z,theta,phi) for running Geant4, config ID, and the number of files/photons produced so far.
        """
        with closing(self._conn.cursor()) as cur:
            if self.get_project(project) is None:
                print('Project',project,'does not exist')
                return None
            table_index = self.table_id(project,config_id)
            cur.execute(f'SELECT config_id,x,y,z,theta,phi,pos_id,dir_id,file_ctr,photon_ctr FROM cfg_{project}{table_index} WHERE config_id={config_id}')
            res=cur.fetchall()
            if len(res)<1:
                print('Project',project,'config_id',config_id,'does not exist')
                return None
            res=res[0]
            res=dict(config_id=res[0],
                     x=res[1],y=res[2],z=res[3],
                     theta=res[4],phi=res[5],
                     pos_id=res[6],dir_id=res[7],
                     file_ctr=res[8],
                     photon_ctr=res[9],)
            return res
    

    def list_positions(self,project:str,pos_id:int=None):
        """List the positions used for the data production

        Retrieve 3D positions to be sampled for the specified project.
        If pos_id is provided, returns the 3D position corresponding to this key.

        Parameters
        ----------
        project : str
            The name of a project to access in the database

        pos_id : int (optional)
            The position ID. If provided, the return is a single XYZ position

        Returns
        -------
        ndarray
            Shape (N,3) where N is the number of positions
        """
        with closing(self._conn.cursor()) as cur:
            cmd = f"SELECT val0,val1,val2,geo_id FROM geo_{project} WHERE geo_type = 0 "
            if pos_id:
                cmd += f"AND geo_id={pos_id} "
            cur.execute(cmd)
            return np.array(cur.fetchall()).astype(float)

    

    def list_directions(self,project:str,dir_id:int=None):
        """List the directions used for the data production

        Retrieve 3D directions to be sampled for the specified project.
        If dir_id is provided, returns the 3D direction corresponding to this key.

        Parameters
        ----------
        project : str
            The name of a project to access in the database

        dir_id : int (optional)
            The direction ID. If provided, the return is a single direction

        Returns
        -------
        ndarray
            Shape (N,3) where N is the number of directions
        """
        with closing(self._conn.cursor()) as cur:
            cmd = f"SELECT val0,val1,geo_id FROM geo_{project} WHERE geo_type = 1 "
            if dir_id:
                cmd += f"AND geo_id={dir_id} "
            cur.execute(cmd)
            return np.array(cur.fetchall()).astype(float)

    def list_voxels(self,project:str,vox_id:int=None):
        """List the voxels used for the data production

        Retrieve vertices of the voxel volume to be sampled for the specified project.
        If vox_id is provided, returns the voxel vertices to this key.

        Parameters
        ----------
        project : str
            The name of a project to access in the database

        vox_id : int (optional)
            The voxel ID. If provided, the return is a single voxel with 6 vertices R,Phi,Z

        Returns
        -------
        ndarray
            Shape (N,6) where N is the number of voxels
        """
        with closing(self._conn.cursor()) as cur:
            cmd = f"SELECT val0,val1,val2,val3,val4,val5,geo_id FROM geo_{project} WHERE geo_type = 2 "
            if vox_id:
                cmd += f"AND geo_id={vox_id} "
            cur.execute(cmd)
            return np.array(cur.fetchall()).astype(float)

    
    def get_random_config(self,project:str,prioritize:bool=True,size:int=1000):
        """Retrieve a job configuration to run in the production

        Sample and retrieve a job configuration from the database.
        The function prioritizes those configurations with low simulation statistics.

        Parameters
        ----------
        project : str
            The name of a project to access in the database

        prioritize : bool (optional)
            If True (default), those configurations with less stats would be prioritized

        size : int (optional)
            The number of configurations to perform a random sampling

        Returns
        -------
        dict
            Contains config/table IDs, (x,y,z,theta,phi)-or-(r0,r1,phi0,phi1,z0,z1), and the number of files produced so far
        """
        p = self.get_project(project)
        max_photons = p.num_photons
        with closing(self._conn.cursor()) as cur:
            table_id = -1
            if not prioritize:
                table_id = int(np.random.random()*self.table_count(project))
            else:
                cmd = f"SELECT table_id FROM map_{project} WHERE photon_ctr <= target_ctr AND lock < 1 ORDER BY photon_ctr ASC LIMIT 1"
                cur.execute(cmd)
                res = cur.fetchall()
                if len(res)<1:
                    print("No result to be prioritized: the production is finished.")
                    return None
                table_id = res[0][0]
            if p._n_phi_start == 0:
                cmd = f"SELECT config_id,x,y,z,theta,phi,file_ctr FROM cfg_{project}{table_id} WHERE photon_ctr < {max_photons}"
        
            else:
                cmd = f"SELECT config_id,r0,r1,phi0,phi1,z0,z1,file_ctr FROM cfg_{project}{table_id} WHERE photon_ctr < {max_photons}"

                
            if prioritize:
                cmd += f" ORDER BY photon_ctr ASC"
            if size>0:
                cmd += f" LIMIT {size}"
            cur.execute(cmd)
            res = cur.fetchall()
            
            seed = round(time.time()*1.e6) % (2**32)
            np.random.seed(seed)
            res = res[int(np.random.random()*len(res))]

            if p._n_phi_start == 0:                
                return dict(config_id=res[0],table_id=table_id,
                            x=res[1],y=res[2],z=res[3],theta=res[4],phi=res[5],
                            file_ctr=res[6],
                )
            else:
                return dict(config_id=res[0],table_id=table_id,
                            r0=res[1],r1=res[2],phi0=res[3],phi1=res[4],z0=res[5],z1=res[6],
                            file_ctr=res[7],
                            )

    def lock_table(self,project:str,table_id:int=None):
        """Lock tables with the specified table ID

        Lock the specified table ID so that it is excluded from the get_random_config function.
        If the table_id is unspecified, all tables will be locked.

        Parameters
        ----------
        project : str
            The name of a project to access in the database

        table_id : int (optional)
            If provided, limit the query to the specified subgroup (table) 
        """

        with closing(self._conn.cursor()) as cur:

            if table_id is None:
                cmd = f"UPDATE map_{project} SET lock = 1"
                cur.execute(cmd)

            else:
                cmd = f"UPDATE map_{project} SET lock = 1 WHERE table_id = {int(table_id)}"
                cur.execute(cmd)

            # finish transaction
            self._conn.commit()


    def unlock_table(self,project:str,table_id:int=None):
        """Unlock tables with the specified table ID

        Unlock the specified table ID so that it is included by the get_random_config function.
        If the table_id is unspecified, all tables will be locked.

        Parameters
        ----------
        project : str
            The name of a project to access in the database

        table_id : int (optional)
            If provided, limit the query to the specified subgroup (table) 
        """

        with closing(self._conn.cursor()) as cur:

            if table_id is None:
                cmd = f"UPDATE map_{project} SET lock = 0"
                cur.execute(cmd)

            else:
                cmd = f"UPDATE map_{project} SET lock = 0 WHERE table_id = {int(table_id)}"
                cur.execute(cmd)

            # finish transaction
            self._conn.commit()


    def list_files(self,project:str,config_id:int=None,table_id:int=None):
        """Retrieve a list of files produced in the production

        Download a list of files produced (for a specific config_id and table_id, if provided)

        Parameters
        ----------
        project : str
            The name of a project to access in the database

        config_id : int (optional)
            If provided, limit the query to the specified configuration

        table_id : int (optional)
            If provided, limit the query to the specified subgroup (table)

        Returns
        -------
        list
            The paths to the produced files.
        """        
        if config_id is not None:
            check = self.table_id(project,config_id)
            if table_id is None:
                table_id = check
            else:
                assert check == table_id
        table_ids = []
        if table_id is None:
            table_ids = np.arange(self.table_count(project))
        else:
            table_ids = [table_id]
        
        flist=[]
        with closing(self._conn.cursor()) as cur:
            for table_index in table_ids:
                cmd = f"SELECT file_path FROM file_{project}{table_index} "
                if config_id:
                    cmd += f"WHERE config_id={config_id}"
                cur.execute(cmd)
                flist = flist + [fs[0] for fs in cur.fetchall()]
        return flist

    
    def exist_file(self,project:str,file_path:str):
        """Check if a file is already in the database

        Loop over file tables and check if the specified file exists in the project

        Parameters
        ----------
        project : str
            The name of a project to access in the database

        file_path : str (optional)
            The path to the file to be checked

        Returns
        -------
        bool
            True = file exists in the database
        """
        file_path = os.path.abspath(file_path)
        with closing(self._conn.cursor()) as cur:
            table_count = self.table_count(project)
            for table_index in range(table_count):
                cmd = f"SELECT file_path FROM file_{project}{table_index} WHERE file_path='{file_path}'"
                cur.execute(cmd)
                res = cur.fetchall()
                if len(res)>0:
                    return True
            return False
        
    
    def exist_table(self,table_name:str):
        """Check if the table exists in the database

        Parameters
        ----------
        table_name : str
            The name of a table

        Returns
        -------
        bool
            True = table exists in the database
        """
        cmd=f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
        with closing(self._conn.cursor()) as cur:
            cur.execute(cmd)
            return len(cur.fetchall())>0
                

    def exist_project(self,project:str):
        """Check if the project exists in the database

        Parameters
        ----------
        project : str
            The name of a project to access in the database

        Returns
        -------
        bool
            True = project exists in the database
        """
        with closing(self._conn.cursor()) as cur:
            cur.execute(f"SELECT name FROM project")
            result = [v[0] for v in cur.fetchall()]
        return project in result
    

    def table_count(self,project:str):
        """Check the number of sub-tables

        Retrieve the number of sub-tables (configuration and file) for the project.
        The sub-tables are made for a big project with many configurations.
        A big project can have hundreds of millions of configurations, too large to be stored in single table.
        Instead, they are divided into roughly equal sized sub-tables.

        Parameters
        ----------
        project : str
            The name of a project to access in the database

        Returns
        -------
        int
            The number of sub-tables
        """
        with closing(self._conn.cursor()) as cur:
            cmd = f"SELECT COUNT(*) FROM map_{project}"
            cur.execute(cmd)
            res = cur.fetchall()[0][0]
            return res

    
    def table_id(self,project:str,config_id:int):
        """Retrieve the sub-table ID that contains the specified configuration.

        Parameters
        ----------
        project : str
            The name of a project to access in the database

        config_id : int
            The configuration ID key

        Returns
        -------
        int
            The configuration table ID
        """
        with closing(self._conn.cursor()) as cur:
            cmd = f"SELECT table_id FROM map_{project} WHERE config_range_min <= {config_id} AND {config_id} <= config_range_max"
            cur.execute(cmd)
            res = cur.fetchall()
            if len(res) < 1:
                raise ValueError(f"invalid config id: {config_id}")
            if len(res) > 1:
                raise RuntimeError(f"Found >1 table id ({res}) corresponding to the config id {config_id}")
            return res[0][0]
    

    def register_project(self,p:wcprod_project,max_entries_per_table:int=1000000):
        """Register a new project

        Register a new project information from wcprod_project instance.
        Can specify the size of sub-tables: keep it in the order of 1E6 for reasonably fast queries.

        Parameters
        ----------
        project : str
            The name of a project to access in the database

        max_entries_per_table : int
            The maximum size of single configuration/file database table. 

        """
        if self.exist_project(p.project):
            raise ValueError(f'Project with the name {p.project} already exists in the database')
            
        # create dataframes to create configuration tables.
        coords = p.configs
        num_tables = int(np.ceil(len(coords) / max_entries_per_table))
        entries = [int(len(coords)/num_tables)]*num_tables
        entries[-1] += (len(coords) - sum(entries))
        assert sum(entries) == len(coords)

        with closing(self._conn.cursor()) as cur:

            project = p.project
            cfg_tablename = f'cfg_{project}'
            file_tablename = f'file_{project}'
            
            # Register the project
            print('Registering project',project)
            cmd = f"INSERT INTO project (name, rmin, rmax, zmin, zmax, gap_space, gap_angle, n_phi_start, num_config, num_tables, num_photons)"
            cmd += f" VALUES ('{p.project}', {p.rmin}, {p.rmax}, {p.zmin}, {p.zmax}, {p.gap_space}, {p.gap_angle}, {p.n_phi_start}, {len(p.configs)}, {num_tables}, {p.num_photons})"
            #print(cmd)
            cur.execute(cmd)

            # Create a management table
            print('Creating a cross-table management db')
            cmd = f"CREATE TABLE map_{project} (table_id INTEGER PRIMARY KEY, config_range_min INT, config_range_max INT, photon_ctr INT, target_ctr INT, lock int)"
            cur.execute(cmd)
            
            # Create a geometry table
            print('Creating a geometry table')
            cmd = f"CREATE TABLE geo_{project} (geo_type INT, geo_id INT, val0 FLOAT, val1 FLOAT, val2 FLOAT, val3 FLOAT, val4 FLOAT, val5 FLOAT)"
            cur.execute(cmd)
            df=pd.DataFrame(dict(geo_type=np.zeros(len(p.positions),dtype=int),
                                 geo_id=np.arange(len(p.positions),dtype=int),
                                 val0=p.positions[:,0],
                                 val1=p.positions[:,1],
                                 val2=p.positions[:,2],
                                 )
            ) 
            df.to_sql(f"geo_{project}",self._conn,if_exists='append',index=False)
            df=pd.DataFrame(dict(geo_type=np.ones(len(p.directions),dtype=int),
                                 geo_id=np.arange(len(p.directions),dtype=int),
                                 val0=p.directions[:,0],
                                 val1=p.directions[:,1],
                                )
            )
            df.to_sql(f"geo_{project}",self._conn,if_exists='append',index=False)
            df = pd.DataFrame(dict(geo_type=np.full(len(p.voxels), 2, dtype=int),
                                   geo_id=np.arange(len(p.voxels), dtype=int),
                                   val0=p.voxels[:, 0],
                                   val1=p.voxels[:, 1],
                                   val2=p.voxels[:, 2],
                                   val3=p.voxels[:, 3],
                                   val4=p.voxels[:, 4],
                                   val5=p.voxels[:, 5],
                                   )
            )
            df.to_sql(f"geo_{project}", self._conn, if_exists='append', index=False)

            # Create a configuration table
            print(f'Creating configuration and file tables: {num_tables} tables covering ({len(p.configs)} entries, can take time...)')
            for table_index in tqdm(range(num_tables)):
                start = sum(entries[:table_index])
                end   = sum(entries[:(table_index+1)])
                #print(np.arange(start,end).astype(int).shape,np.zeros(shape=(end-start),dtype=int).shape,coords[start:end,5].astype(int).shape,coords[start:end,6].astype(int).shape,coords[start:end,3].shape,coords[:,4].shape)
                if p.n_phi_start == 0:
                    df=pd.DataFrame(dict(config_id=np.arange(start,end).astype(int),
                                         x=coords[start:end,0],y=coords[start:end,1],z=coords[start:end,2],
                                         theta=coords[start:end,3],phi=coords[start:end,4],
                                         pos_id=coords[start:end,5].astype(int),
                                         dir_id=coords[start:end,6].astype(int),
                                         file_ctr=np.zeros(shape=(end-start),dtype=int),
                                         photon_ctr=np.zeros(shape=(end-start),dtype=int),
                                        )
                                    )
                else:
                    df = pd.DataFrame(dict(config_id=np.arange(start, end).astype(int),
                                           r0=coords[start:end, 0], r1=coords[start:end, 1],
                                           phi0=coords[start:end, 2], phi1=coords[start:end,3],
                                           z0=coords[start:end, 4], z1=coords[start:end,5],
                                           pos_id=coords[start:end, 6].astype(int),
                                           dir_id=np.zeros(shape=(end-start), dtype=int),
                                           file_ctr=np.zeros(shape=(end - start), dtype=int),
                                           photon_ctr=np.zeros(shape=(end - start), dtype=int),
                                           )
                                      )
                df.to_sql(cfg_tablename+str(table_index),self._conn, index=False)
                cur.execute(f"ALTER TABLE {cfg_tablename}{table_index} ADD Timestamp DATETIME")
                current_timestamp = datetime.datetime.now().isoformat(" ",timespec='seconds')
                cur.execute(f"UPDATE {cfg_tablename}{table_index} SET Timestamp = '{current_timestamp}'")

                # Create a file table
                cur.execute(f"CREATE TABLE {file_tablename}{table_index} (file_id INTEGER PRIMARY KEY AUTOINCREMENT, config_id INT, file_path STRING, photon_ctr INT, duration FLOAT, Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
                
                # Register the table ID 
                cmd  = f"INSERT INTO map_{project} (table_id, config_range_min, config_range_max, photon_ctr, target_ctr, lock) "
                cmd += f"VALUES ({table_index}, {start}, {end-1}, 0, {len(df)*(p.num_photons)}, 0)"
                cur.execute(cmd)
                
            self._conn.commit()
            print('Running integrity check')
            self.check_integrity(project)
            print('Successfully created project',project)



    def drop_project(self,project:str):
        """Drop a project from the database

        Parameters
        ----------
        project : str
            The name of a project to access in the database

        """
        if not self.exist_project(project):
            raise ProjectNotFoundError(f"Project '{project}' not found in the project table.")

        num_tables = self.table_count(project)
        with closing(self._conn.cursor()) as cur:
            for index in range(num_tables):
                cmd = f"DROP TABLE cfg_{project}{index}"
                cur.execute(cmd)
                cmd = f"DROP TABLE file_{project}{index}"
                cur.execute(cmd)
            cmd = f"DROP TABLE map_{project}"
            cur.execute(cmd)
            cmd = f"DROP TABLE geo_{project}"
            cur.execute(cmd)
            cmd = f"DELETE FROM project WHERE name='{project}'"
            cur.execute(cmd)
        self._conn.commit()
        
    def register_file(self,project:str,config_id:int,file_path:str,num_photons:int,duration:float):    
        """Register a new file

        Register a new file location in the final storage space to the database

        Parameters
        ----------
        project : str
            The name of a project to access in the database

        config_id : int
            The configuration ID used to produce this file

        file_path : str
            The full path to the final storage location of this file

        num_photons : int
            The number of photons produced in the file

        duration : float
            The time in seconds that has taken to produce this file
        """
        # Check if the file exists and physical
        if not os.path.isfile(file_path):
            print('File not exist:',file_path)
            return False
        
        file_path = os.path.abspath(file_path)
        
        # Check if the config id is valid
        if self.get_config(project,config_id) is None:
            return False
        
        # Check if the same path exists in the DB already
        if self.exist_file(project,file_path):
            print('File already registered in the DB')
            return False
        
        # Register
        with closing(self._conn.cursor()) as cur:
                            
            # retrieve the table id
            table_id = self.table_id(project,config_id)
            cmd = f"INSERT INTO file_{project}{table_id} (config_id,file_path,photon_ctr,duration) VALUES ({config_id},'{file_path}',{num_photons},{duration});"
            cur.execute(cmd)

            current_timestamp = datetime.datetime.now().isoformat(" ",timespec='seconds')
            cmd = f"UPDATE cfg_{project}{table_id} SET file_ctr = file_ctr+1, photon_ctr = photon_ctr+{num_photons}, Timestamp = '{current_timestamp}' WHERE config_id = {config_id};"
            cur.execute(cmd)
            
            cmd = f"UPDATE map_{project} SET photon_ctr = photon_ctr + {num_photons} WHERE table_id = {table_id}"
            cur.execute(cmd)
            # Check if it's registered correctly
            
            
            # finish transaction
            self._conn.commit()
