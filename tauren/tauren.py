"""
Tauren-MD trajectory objects.
"""
# Copyright © 2018-2019 Tauren-MD Project
#
# Tauren-MD is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Tauren-MD is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Tauren-MD. If not, see <http://www.gnu.org/licenses/>.
#
# Contributors to this file:
# - João M.C. Teixeira (https://github.com/joaomcteixeira)
import sys
import string
import numpy as np
import json

from abc import ABC, abstractmethod

import mdtraj
import MDAnalysis as mda
from MDAnalysis.analysis import align as mdaalign
from MDAnalysis.analysis.rms import RMSD as mdaRMSD

from tauren import logger, core, _errors

log = logger.get_log(__name__)


class TaurenTraj(ABC):
    """
    Base class for Tauren-MD sub Traj classes.
    """
    
    _err_frame_index = \
        "    frame '{}' does NOT exist in trajectory, ignoring..."
    
    filenametranslation = str.maketrans(",:() ", "----_")
    
    @core.log_args
    def __init__(self, trajectory, topology):
        
        self.trajpath = trajectory
        self.topopath = topology
        
        self._set_full_frames_list()
        self._update_traj_slicer(
            start=0,
            end=len(self.full_frames_list),
            step=1
            )
        
        self.observables = None
        self._rmsds_counter = 0
        
        return
    
    # @property
    # @abstractmethod
    # def trajectory(self):
        # """
        # Returns the trajectory object.
        # """
        # pass
    
    @property
    def original_traj(self):
        """
        The original trajectory without any modification.
        """
        return self._original_traj
    
    @original_traj.setter
    def original_traj(self, traj):
        self._original_traj = traj
    
    @property
    @abstractmethod
    def trajectory(self):
        """
        The trajectory sliced according to the current
        :attr:`~atom_selection`.
        
        For :doctrajtype:`trajectory type <>` :mdtrajdoc:`MDTraj <>`
        *trajectory* is sliced also according to :attr:`~slice_tuple`.
        """
        pass
    
    @trajectory.setter
    def trajectory(self):
        log.info("* CANT manually set a sliced traj. Ignoring...")
        return None
    
    @property
    def observables(self):
        """A list containing all data obtained from the system."""
        return self._observables
    
    @observables.setter
    def observables(self, obs=None):
        self._observables = obs or TrajObservables()
    
    @abstractmethod
    def _set_full_frames_list(self, num_frames):
        """
        Defines the list of frames in the input trajectory.
        """
        self._full_frames_list = list(range(1, num_frames + 1))
    
    @property
    def full_frames_list(self):
        """
        The list of frames in the input trajectory.
        """
        return self._full_frames_list
    
    @full_frames_list.setter
    def full_frames_list(self):
        log.info("* NOTICE * Can't set full_frames_list manually")
    
    @property
    def sliced_frames_list(self):
        """
        The list of frames in the current frame slicing,
        according to :attr:`~slice_tuple`.
        """
        return self.full_frames_list[self._fslicer]
    
    @property
    def slice_tuple(self):
        """
        A 3 element tuple identifing the current frame slicing,
        (start, end, step), where start is 0-indexed, end is excluded.
        """
        return self._slice_tuple
    
    @slice_tuple.setter
    def slice_tuple(self, tuple_):
        """
        Tuple (start, end, step)
        """
        self._check_correct_slice(
            tuple_[0],
            tuple_[1],
            tuple_[2],
            )
        
        log.info(f"slice_tuple: {tuple_}")
        
        self._slice_tuple = tuple_
        
        return
    
    @property
    def n_frames(self):
        """
        The number of frames in the trajectory considering the
        current slicing as defined by the :attr:`~slice_tuple`.
        """
        return len(self.full_frames_list[self._fslicer])
    
    @property
    @abstractmethod
    def totaltime(self):
        """
        The total time in the current slicing, according to
        :attr:`~slice_tuple`
        """
        pass
    
    @property
    @abstractmethod
    def timestep(self):
        """
        The time step in the current slicing, according to
        :attr:`~slice_tuple`
        """
        pass
    
    @property
    def atom_selection(self):
        """
        String that defines the current atom selection.
        
        If not defined assumes "all".
        """
        try:
            return self._atom_selection
        
        except AttributeError:
            return "(all)"
    
    @atom_selection.setter
    def atom_selection(self, selector):
        """
        String that defines the current atom selection.
        
        Parameters
        ----------
        selector : str
            The string the defines the selector.
        """
        
        if selector is None or selector == "all":
            self._atom_selection = "all"
        
        elif not isinstance(selector, str):
            raise TypeError(
                "*selector* must be STRING type."
                f" '{type(selector)}' given."
                )
        
        else:
            self._atom_selection = f"({selector})"
    
    @property
    @abstractmethod
    def n_residues(self):
        """
        The number of residues in the current slicing,
        according to :attr:`~atom_selection`.
        """
        pass
    
    @property
    @abstractmethod
    def n_atoms(self):
        """
        The number of atoms in the current slicing,
        according to :attr:`~atom_selection`.
        """
        pass
    
    @core.log_args
    def _update_traj_slicer(
            self,
            start,
            end,
            step,
            ):
        """
        Updates the current frame slicing object.
        
        *start* and *end* are ¡Python indexes!, where
        *start* starts from 0 and *end* is NOT included.
        """
        self.slice_tuple = (start, end, step)
        self._fslicer = slice(start, end, step)
        
        log.debug(f"<_fslicer> updated: {self._fslicer}")
        
        return
    
    @core.log_args
    def _check_correct_slice(self, start, end, step):
        """
        Checks if slicing is valid and gives NOT an empty selection.
        """
        
        if not isinstance(start, int) \
                and not isinstance(end, int) \
                and not isinstance(step, int):
            
            raise TypeError("arguments must be INTEGER type")
        
        slc = slice(start, end, step)
        
        try:
            fflst = self.full_frames_list[slc]
        
        except ValueError:
            log.info("*step* can NOT be zero.")
            raise
        
        if not fflst:
            
            raise ValueError(
                f"This tuple combination '{(start, end, step)}'"
                " will render an empty selection."
                )
        
        return
    
    def report(self):
        """Prints general information about trajectory."""
        
        info = (
            "* Trajectory details:\n"
            "\n"
            f"    num of frames: {self.n_frames}\n"
            f"    num of residues: {self.n_residues}\n"
            f"    num of atoms: {self.n_atoms}\n"
            "\n"
            f"    total time: {self.totaltime:.3f}\n"
            "\n"
            f"    time_step: {self.timestep:.3f} (usually ps)\n"
            f"        or {(self.timestep / 1000):.3f} (usually ns)\n"
            "*\n"
            )
        
        log.info(info)
        
        return info
    
    @core.log_args
    def remove_solvent(self, **kwargs):
        """
        Removes solvent from trajectory.
        
        Parameters
        ----------
        exclude : :obj:`list`
            Available only when using :mdtrajdoc:`MDTraj <>`
            as :doctrajtype:`trajectory type <>`.
            List of solvent residue names to retain in the new
            trajectory.
            Defaults to None.
            :mdtdocrmvsol:`MDTraj remove_solvent documentation <>`.
        """
        log.info("* Removing solvent...")
        self._remove_solvent(**kwargs)
    
    @abstractmethod
    def _remove_solvent(self):
        pass
    
    def undo_rmv_solvent(self):
        """
        Undo a previous action of solvent removal by activating
        solvent again.
        """
        self._undo_rmv_solvent()
    
    @abstractmethod
    def _undo_rmv_solvent(self):
        pass
    
    @core.log_args
    def align_traj(
            self,
            *,
            inplace=True,
            file_name="aligned_traj.dcd",
            **kwargs,
            ):
        """
        Aligns trajectory to the topology (reference).
        
        Currently only implemented for :mdanalysis:`MDAnalysis <>`
        subroutines.
        
        Parameters
        ----------
        inplace : :obj:`bool`
            Whether to align the trajectory in place or export the
            aligned trajectory to a new object/file.
            If ``False``, *file_name* is used.
            Defaults to ``True``.
            
            **MDAnalysis:**
                Does NOT return new object, saves aligned trajectory
                to new file instead.
        
        file_name : :obj:`str`
            The name of the file of the aligned trajectory.
            Trajectory type is deduced from file extension.
            User only if *inplace* is ``True``, ignored otherwise.
        
        Raises
        ------
        TypeError
            If *file_name* is not :obj:`str` type.
            If *inplace* is not :obj:`bool` type.
        """
        
        log.info("* Aligning trajectory... ")
        
        if not(isinstance(file_name, str)):
            raise TypeError("file_name is NOT str type.")
        
        if not(isinstance(inplace, bool)):
            raise TypeError("inplace is NOT bool.")
        
        kw = {
            "file_name": file_name,
            "inplace": inplace,
            }
        
        tmp = self._align_traj(**{**kwargs, **kw})
        
        log.info("    done")
        
        return tmp
    
    @abstractmethod
    def _align_traj(self):
        return
        
    def image_molecules(self, **kwargs):
        """
        Images molecules.
        
        Currently only available for :mdtrajdoc:`MDTraj <>`
        subroutines.
        
        Images molecules according to :mdjdocim:`MDTraj.image_molecules <>`.
        Receives the same arguments.
        """
        
        return self._image_molecules(**kwargs)
    
    @abstractmethod
    def _image_molecules(self):
        return
    
    @core.log_args
    def frame_slice(
            self,
            start=None,
            end=None,
            step=1,
            ):
        """
        Slices trajectory in frames for the subsequent operations.
        
        Parameters
        ----------
        start : int
            The starting frame.
            Frame index starts at 1.
            Defaults to None, slices from the first frame.
        
        end : int
            The end frame for the new slicing (INCLUSIVE).
            END should be lower or equal than the traj length.
            Defaults to None, slices to the last frame.
        
        step : int
            Integer value which determines the increment between
            each index for slicing.
            Defaults to 1.
        
        Exceptions
        ----------
        TypeError
            If any parameter is not integer type.
        
        ValueError
            If slice renders empty selection.
        """
        
        # assigns default values here because
        # None values can be received from the config.json file
        start = start or 1
        end = end or len(self.full_frames_list)
        step = step or 1
        
        log.info(f"* Slicing trajectory [{start}, {end}, {step}]...")
        self._update_traj_slicer(start - 1, end, step)
        log.info("    done.")
        return
    
    @core.log_args
    def set_atom_selection(self, selector, **kwargs):
        """
        Sets the atom selection.
        
        Atom selection will be used in subsequent operations.
        
        Parameters
        ----------
        selector : :obj:`str`.
            The selection string.
            If None type provided assumes ``"all"``.
            Should be of a valid format according to the
            MD analysis library used in :doctrajtype:`trajectory_type <>`.
            Please refer to the MD analysis library
            specific documentation:
            
            - :mdaselections:`MDAnalysis <>`
            - :mdtselections:`MDTraj <>`
        
        Raises
        ------
        TypeError
            If selection is not string.
        """
        log.info("* Setting atom selection:")
        log.debug(f"<selection>: {selector}")
        
        if selector is None or selector == "all":
            self.atom_selection = "all"
        
        else:
            self.atom_selection = selector
        
        log.info(f"    atom selection set to {self.atom_selection}")
        
        return
    
    @core.log_args
    def frames2file(
            self,
            frames="all",
            prefix="_",
            ext="pdb",
            ):
        """
        Extracts trajectory frames to PDB files using prefix name.
        
        Parameters
        ----------
        frames : str, optional
            Frame or range of frames to extract.
            Defaults to "all": extract all frames from current slicing.
            
            A frame range can be defined as follows:
            End values are INCLUSIVE.
                - "1"           -> the first frame
                - "1,5,100"     -> frames 1, 5 and 100
                - "10:"         -> from frame 10 to the end
                - ":500"        -> from first frame to frame 500 (inclusive)
                - "10:50"       -> from frame 10 to 50 (inclusive)
                - "10:100:2"    -> from frame 10 to 100 in steps of 2
        
        prefix : str, optional
            The prefix name for extracted PDBs.
            Defaults to "_".
        
        ext : str, optional ["pdb"]
            The file extention to which the frames are saved.
            Deppending on the trajectory type used the allowed
            file types may differ. Reffer to the documentation of
            the MD analysis library you are using.
        
        Exceptions
        ----------
        TypeError
            If *frames* is not of string type.
            
        ValueError
            If *frames* string is not consistent with parameter
            description.
        """
        
        log.info("* Extracting frames...")
        
        log.debug(f"<frames>: {frames}")
        log.debug(f"<prefix>: {prefix}")
        log.debug(f"<ext>: {ext}")
        
        if isinstance(frames, str) and frames.startswith("0") \
                or isinstance(frames, int) and frames == 0 \
                or isinstance(frames, list) and 0 in frames:
            raise ValueError("Trajectory frames indexes start at 1.")
        
        frames_to_extract = self._get_frame_list(frames)
        
        pdb_name_fmt = \
            prefix \
            + self._gen_pdb_name_format(len(self.full_frames_list), ext)
        
        assert isinstance(frames_to_extract, list), (
            "<frames_to_extract> should be LIST! "
            f"{type(frames_to_extract)} given"
            )
        
        assert isinstance(pdb_name_fmt, str), (
            "<pdb_name_format> should be string type. "
            f"{type(pdb_name_fmt)} given"
            )
        
        self._frames2file(frames_to_extract, pdb_name_fmt)
        
        log.info("    frames extracted successfully!")
        
        return
    
    @core.log_args
    def _get_frame_list(self, frames):
        """
        Extract the frame number sublist from *frames*.
        
        *frames* can be INT or STR.
        
        Frames list self.full_frames_list is indexed at 1.
        """
        if frames == "all":
            return self.sliced_frames_list
        
        elif isinstance(frames, int):
            return [self.full_frames_list[frames - 1]]
        
        elif isinstance(frames, str):
            
            if frames.isdigit():
                return [self.full_frames_list[int(frames) - 1]]
            
            elif frames.replace(",", "").isdigit():
                # _ for flake8 :-)
                _ = self.full_frames_list
                return [_[int(f) - 1] for f in frames.split(",") if f]
                
            elif ":" in frames and frames.replace(":", "").isdigit():
                
                slicer = self._gen_frame_slices_from_string(frames)
                self._check_correct_slice(*slicer)
                return self.full_frames_list[slice(*slicer)]
            
            else:
                raise ValueError("*frames* string not of valid format")
        
        else:
            raise TypeError(
                f"*frames* should be STRING type: '{type(frames)}' given."
                )
    
    @core.log_args
    def _gen_frame_slices_from_string(self, s):
        """
        Generates slices indexes from string.
        
        Examples:
            
            >>> _gen_frame_slicer_from_string("1")
            (0, 1, 1)
            
            >>> _gen_frame_slicer_from_string("1:100")
            (0, 100, 1)
        
        Returns
        -------
        tuple
            (start, end, step) indexes.
        """
        
        if s.isdigit():
            start = int(s) - 1
            end = int(s)
            step = 1
        
        elif s.endswith(":") and s.count(":") == 1:
            ss = s.split(":")
            start = int(ss[0]) - 1
            end = len(self.full_frames_list)
            step = 1
        
        elif s.startswith(":") and s.count(":") == 1:
            ss = s.split(":")
            start = 0
            end = int(ss[1])
            step = 1
        
        elif s.count(":") == 1:
            ss = s.split(":")
            start = int(ss[0]) - 1
            end = int(ss[1])
            step = 1
        
        elif s.count(":") == 2 \
                and not(s.startswith(":")) \
                and len(s.split(":")) == 3:
            
            ss = s.split(":")
            start = int(ss[0]) - 1
            end = int(ss[1])
            step = int(ss[2])
        
        elif s.startswith("::") and s[2:].isdigit():
            start = 0
            end = len(self.full_frames_list)
            step = int(s[2:])
        
        else:
            raise ValueError("slice string not valid")
        
        return start, end, step
    
    @staticmethod
    @core.log_args
    def _gen_pdb_name_format(num_of_frames, ext):
        """
        Creates a formatting string to apply leading zeros.
        
        Parameters
        ----------
        num_of_frames : int or str
            The number of frames.
        
        ext : str
            The file extension.
        """
        
        leading_zeros = str(len(str(num_of_frames)))
        pdb_name_fmt = "{:0>" + leading_zeros + "}." + f"{ext}"
        
        return pdb_name_fmt
    
    @abstractmethod
    def _frames2file(self, frames_list, pdb_name_fmt):
        """
        frames_list is a list of integers with the frames to extract.
        frames_list should be indexed at 1 (human way not python way)
        
        pdb_name_fmt is a .format() prepared string where the number
        of the extracted frame will fit in.
        """
        return
    
    @core.log_args
    def save_traj(
            self,
            file_name="traj_output.dcd",
            **kwargs
            ):
        """
        Saves trajectory to file.
        
        Overwrites existing files.
    
        Parameters
        ----------
        file_name : :obj:`str`
            Name of the output trajectory file.
            File extention is taken from file_name.
        """
        log.info(f"* Exporting trajectory to: {file_name}")
    
        self._save_traj(file_name)
    
        log.info("    ... saved")
        
        return
    
    @abstractmethod
    def _save_traj(self, file_name):
        """The subclass algorithm to save a trajectory."""
        pass
    
    @core.log_args
    def calc_rmsds_combined_chains(
            self,
            *,
            chains="all",
            ref_frame=0,
            storage_key="rmsds_combined_chains",
            **kwargs
            ):
        """
        Calculates combined RMSDs for a set of chains.
        
        Parameters
        ----------
        chains : str or list of identifiers, optional
            Defaults to "all", all chains are used.
            Previous selection is considered, therefore, chains
            will subselect over the current
            :meth:`~TaurenTraj.set_atom_selection`.
            
            With str, use: "1" or comma separated identifers, "1,2,4".
            
            With list, use a list of identifiers: [1,2,4] or ["A", "D"].
            
            **Remember that:**
            # when using **MDAnalysis**, identifiers are the segid
            characters.
            # when using **MDTraj**, identifiers are digits that
            represent chain order.
        
        ref_frame : int, optional
            The reference frame for the RMSD calculation.
        
        storage_key : str, optional
            A general naming string to identify the results calculated
            with this method.
            Defaults to "rmsds_combined_chains".
        
        **kwargs
            Any other kwargs passed will be stored in the results
            dictionary at :attr:`~observables`. Specific names of this
            method will overwrite named arguments with the same name.
            Specific names (keys) include: data, selection, identifier,
            ref_frame, columns, name.
        
        Returns
        -------
        int
            The index in which data was stored in :attr:`~observables`
            attribute.
        
        Exceptions
        ----------
        TypeError
            If chains is not list or string.
        
        ValueError
            If chains str or list is not of valid format (read above).
        
        IndexError
            If trajectory can not be sliced according to chains.
        """
        
        log.info("* Calculating RMSDs for combined chains...")
        
        storage_key = storage_key or "rmsds_combined_chains"
                
        chain_list = self._gen_chain_list(chains)  # abstractmethod
        
        combined_rmsds, column_headers = self._calc_rmsds_combined_chains(
            chain_list,
            ref_frame,
            )
        
        assert combined_rmsds.ndim == 1, (
            "<combined_rmsds> array should have only one dimension. "
            f"Detected array with {combined_rmsds.ndim}."
            )
        
        frames_array = np.array(self.sliced_frames_list)
        
        assert combined_rmsds.size == frames_array.size, (
            "combined_rmsds and frames_array size does not match. "
            f"{combined_rmsds.size} vs. {frames_array.size}"
            )
        
        data = np.vstack((frames_array, combined_rmsds)).T
        
        chain_name = self._gen_chains_filename(chains)
        
        storagedata = {
            "data": data,
            "solvent": self._solvent_selector,
            "atom_selection": self._atom_selection,
            "identifier": chains,
            "ref_frame": ref_frame,
            "columns": ["frames"] + column_headers,
            "name": (
                f"{storage_key}"
                f"_{self._solvent_selector}"
                f"_{self._atom_selection}"
                f"_{chain_name}"
                ).translate(self.filenametranslation)
            }
        
        self.observables.append(**{**kwargs, **storagedata})
        
        return self.observables.last_index
    
    @abstractmethod
    def _calc_rmsds_combined_chains(self):
        """
        MD analysis library specific implementation.
        
        Parameters
        ----------
        chain_list : list of strs
            List of strings containing the chains to operate with
        
        ref_frame : int
            The reference frame to which calculate te rmsds
        
        Returns
        -------
        numpy.array of shape=(X,)
            The returned array should be sliced according to the
            current frame slicer (self._fslicer).
        
        list of strs
            List of chains IDs evaluated.
        """
        
        pass
        
    # @abstractmethod
    @core.log_args
    def _gen_chain_list(self, chains):
        """
        Genereates a list of chains based on a <chains> string value.
        
        Parameters
        ----------
        chains : str or list of identifiers, optional
            
            With str, use: "1" or comma separated identifers, "1,2,4".
            
            With list, use a list of identifiers: [1,2,4] or ["A", "D"].
            
            If "all" specific subclass method must be called.
        """
        
        def valid(c):
            return (isinstance(c, int)
                    or isinstance(c, str) and (c.isdigit() or c.isalpha()))
        
        if chains == "all":
            return self._gen_chain_list_all()
        
        elif isinstance(chains, int):
            return [str(chains)]
        
        elif isinstance(chains, str):
            # in case split gives empty strings in list
            chains = [c for c in chains.split(",") if c]
        
        if isinstance(chains, list):
        
            if all(valid(c) for c in chains):
                return [str(c) for c in chains]
            
            else:
                raise ValueError(
                    "Values in chains list must be"
                    " STRING letters or digits or INT"
                    )
        
        else:
            raise TypeError("chains must be STRING or LIST type")
    
    @abstractmethod
    def _gen_chain_list_all(self):
        # what each subclass should return when *chains* is "all"
        # in _gen_chain_list()
        pass
    
    def _gen_chains_filename(self, chains):
        """
        Generates a string for file names from *chains* input.
        
        requires *chains* to be processed by _gen_chain_list_all
        to confirm chains is valid.
        """
        
        if chains == "all":
            return chains
        
        else:
            return "-" + "-".join(chains.split(","))
    
    @core.log_args
    def calc_rmsds_separated_chains(
            self,
            *,
            chains="all",
            ref_frame=0,
            storage_key="rmsds_separated_chains",
            **kwargs
            ):
        """
        Calculates RMSDs for each chain separately.
        
        Parameters
        ----------
        chains : str or list of idetifiers, optional
            Defaults to "all", all chains are used.
            
            With str, use: "1" or comma separated identifers, "1,2,4".
            
            With list, use a list of identifiers: [1,2,4] or ["A", "D"].
            
            **Remember that:**
            # when using **MDAnalysis**, identifiers are the segid
            characters.
            # when using **MDTraj**, identifiers are digits that
            represent chain order.
        
        ref_frame : int, optional
            The reference frame for the RMSD calculation.
        
                storage_key : str, optional
            A general naming string to identify the results calculated
            with this method.
            Defaults to "rmsds_combined_chains".
        
        **kwargs
            Any other kwargs passed will be stored in the results
            dictionary at :attr:`~observables`. Specific names of this
            method will overwrite named arguments with the same name.
            Specific names (keys) include: data, selection, identifier,
            ref_frame, columns, name.
        
        Returns
        -------
        int
            The index in which data was stored in :attr:`~observables`
            attribute.
        
        Exceptions
        ----------
        TypeError
            If chains is not list or string.
        
        ValueError
            If chains str or list is not of valid format (read above).
        
        IndexError
            If trajectory can not be sliced according to chains.
        """
        
        log.info("* Calculating RMSDs for each chain separately")
        
        chain_list = self._gen_chain_list(chains)  # abstractmethod
        
        rmsds, chains_headers = self._calc_rmsds_separated_chains(
            chain_list,
            ref_frame=ref_frame,
            )
        
        frames_array = np.array(self.sliced_frames_list)
        
        assert rmsds.shape[0] == frames_array.size, (
            "RMSDs array does not match frames_array size. "
            f"{rmsds.shape[0]} vs. {frames_array.size}."
            )
        
        data = np.concatenate(
            (
                frames_array.reshape(frames_array.size, 1),
                rmsds
                ),
            axis=1,
            )
        
        chain_name = self._gen_chains_filename(chains)
        
        storagedata = {
            "data": data,
            "solvent": self._solvent_selector,
            "atom_selection": self._atom_selection,
            "identifier": chains,
            "ref_frame": ref_frame,
            "columns": ["frames"] + chains_headers,
            "name": (
                f"{storage_key}"
                f"_{self._solvent_selector}"
                f"_{self._atom_selection}"
                f"_{chain_name}"
                ).translate(self.filenametranslation)
            }
        
        self.observables.append(**{**kwargs, **storagedata})
        
        return self.observables.last_index
    
    @abstractmethod
    def _calc_rmsds_separated_chains(self):
        """
        MD analysis library specific implementation.
        
        Parameters
        ----------
        chain_list : list of strs
            List of strings containing the chains to operate with
        
        ref_frame : int
            The reference frame to which calculate te rmsds
        
        Returns
        -------
        numpy.array, shape=(Y,X)
            Where Y is the number of frames and X number of chains.
            The returned array should be sliced according to the
            current frame slicer (self._fslicer).
        
        list of strs
            List of chains IDs evaluated.
        """
        pass
    
    @staticmethod
    @core.log_args
    def _gen_selector(
            identifiers,
            selection="segid",
            boolean="or",
            ):
        """
        Generates a selector for chains, atoms, residues parsing.
        """
        
        log.debug(f"identifier: {identifiers}")
        
        if not isinstance(identifiers, list):
            raise TypeError(
                "*identifiers* must be LIST."
                f" '{type(identifiers)}' given."
                )
        
        id_lst = list(map(lambda x: f"{selection} {x}", identifiers))
        
        selector = f" {boolean} ".join(id_lst)
        
        log.debug(f"selector: {selector}")
        
        assert isinstance(selector, str), "selector should be string"
        return selector
    
    @core.log_args
    def export_data(
            self,
            index,
            prefix='',
            suffix="csv",
            file_name=None,
            sep=",",
            header="",
            tojson=False,
            fmt="%.5f",
            **kwargs,
            ):
        """
        Exports data to file.
        
        Exporting template is selected automatically from data type.
        The *tojson* parameter forces data to be exported to JSON file.
        If data type can be identified, exports to JSON.
        
        Parameters
        ----------
        index : :obj:`int`
            The index of :attr:`~self.observables` where data to export
            is stored.
        
        prefix : :obj:`str`, optional
            A prefix to add to the naming attribute in the key object.
            Defaults to empty string.
            If *file_name* is given, prefix and key naming are not considered.
        
        suffix : :obj:`str`, optional
            The file extention.
            Defaults to 'csv'.
            
        file_name : :obj:`str`, optional
            The name of the file. Prevails over prefix and key naming.
            Defaults to ``None``.
        
        tojson : :obj:`bool`
            If ``True`` exports data dictionary to a JSON file.
            If ``False`` exports according to data type.
            Defaults to ``False``.
        
        sep : :obj:`str`, optional
            The column separator for np.ndarray data type.
            Defaults to comma ``,``.
        
        header : :obj:`str`, optional
            Any text you wish to add as comment as file header.
            Headers are identified by "#".
            Defaults to empty string.
        
        fmt : str
            String formatter in case *data* is Numpy array type.
            According to :npsavetxt:`numpy .savetxt doc <>`.
            Defaults to "%.5f".
        """
        try:
            self.observables[index]
        
        except IndexError:
            log.info(f"*index* '{index}' does not exist in *observables*.")
            log.info("Ignoring...")
            return
        
        filename = self._gen_export_file_name(
            index,
            file_name=file_name,
            prefix=prefix,
            suffix=suffix,
            )
        
        log.info(f"* Exporting {filename}")
        
        log.debug(f"data type: {type(self.observables[index]['data'])}")
        
        if tojson:
            self._export_data_json(index, filename, header)
        
        else:
            if isinstance(self.observables[index]["data"], np.ndarray):
                self._export_data_array(
                    index,
                    filename,
                    sep,
                    header=header,
                    fmt=fmt,
                    )
        
            else:
                self._export_data_json(index, filename, header)
        
        log.info(f"    saved {filename}")
        
        return
    
    @core.log_args
    def _gen_export_file_name(
            self,
            index,
            *,
            file_name=None,
            prefix=None,
            suffix='csv',
            ):
        """
        Generates a filename based on the data information.
        """
        
        tablename = [
            file_name,
            self.observables[index].get("name"),
            self.observables[index].get("storage_key"),
            ]
        
        if prefix:
            prefix += "_"
        
        filename = (
            f"{'' if file_name else (prefix or '')}"
            f"{next((x for x in tablename if x), f'data_index_{index}')}"
            f".{suffix or 'csv'}"
            )
        
        return filename
    
    @core.log_args
    def _export_data_array(
            self,
            index,
            filename,
            sep,
            header='',
            fmt="%.5f",
            ):
        """
        Template to export numpy data.
        """
        
        log.debug("exporting data as array")
        
        for key, value in self.observables[index].items():
            if key == "data":
                continue
            header += f"{key}: {value}\n"
                
        try:
            columns = list(map(
                lambda x: str(x),
                self.observables[index]["columns"],
                ))
        
        except KeyError:
            columns = \
                [f"column_{i}" for i in range(
                    self.observables[index]["data"].shape[0])]
                
        header += ','.join(columns)
        
        log.debug(f"header: {header}")
        
        np.savetxt(
            filename,
            self.observables[index]["data"],
            delimiter=sep,
            header=header,
            fmt=fmt,
            )
        
        return
    
    @core.log_args
    def _export_data_json(self, index, filename, header):
        """
        Template to export data as plain text.
        """
        
        log.debug("exporting data as plain text")
        
        results_copy = self.observables[index].copy()
        
        # adapts data before exporting
        for key, value in results_copy.items():
            if isinstance(value, np.ndarray):
                results_copy[key] = value.tolist()
        
        results_copy["header"] = header
        
        with open(filename, 'w') as fh:
            json.dump(
                results_copy,
                fh,
                indent=4,
                sort_keys=True,
                )
    
        return


class TaurenMDAnalysis(TaurenTraj):
    
    @core.log_args
    def __init__(self, trajectory, topology):
        
        self.universe = mda.Universe(topology, trajectory)
        self.topology = mda.Universe(topology)
        self.original_traj = self.universe.trajectory
        
        # mdanalysis specific method
        self.undo_rmv_solvent()
        
        super().__init__(trajectory, topology)
        
        return
    
    def _set_full_frames_list(self):
        super()._set_full_frames_list(self.original_traj.n_frames)
    
    @TaurenTraj.trajectory.getter
    def trajectory(self):
        return self.universe.select_atoms(self.atom_selection)
    
    @TaurenTraj.totaltime.getter
    def totaltime(self):
        return self.original_traj[self._fslicer][-1].time
    
    @TaurenTraj.timestep.getter
    def timestep(self):
        return (
            self.original_traj[self._fslicer][1].time
            - self.original_traj[self._fslicer][0].time
            )
    
    @TaurenTraj.atom_selection.getter
    def atom_selection(self):
        try:
            atmsel = self._atom_selection
        
        except AttributeError:
            atmsel = "all"
        
        return f"{self._solvent_selector} and {atmsel}"
    
    @TaurenTraj.n_residues.getter
    def n_residues(self):
        return self.universe.atoms.n_residues
    
    @TaurenTraj.n_atoms.getter
    def n_atoms(self):
        return len(self.universe.atoms)
    
    @core.log_args
    def _remove_solvent(self, exclude=None, **kwargs):
        
        if isinstance(exclude, list):
            self._solvent_selector = (
                "(protein or nucleic or "
                f"{'name ' + 'name or'.join(exclude)})"
                )
        
        elif exclude is None:
            self._solvent_selector = "(protein or nucleic)"
        
        else:
            raise TypeError(
                "*exclude* must be LIST type,"
                f" '{type(exclude)} given."
                )
            
        log.info("    solvent removed")
        return
    
    def _undo_rmv_solvent(self):
        log.debug("activated solvent")
        self._solvent_selector = "all"
        return
    
    def _image_molecules(self, **kwargs):
        log.info("image_molecules method not implemented for MDAnalaysis")
        return "not implemented"
    
    @core.log_args
    def _align_traj(
            self,
            file_name="aligned_traj",
            inplace=False,
            **kwargs,
            ):
        
        # https://www.mdanalysis.org/docs/documentation_pages/analysis/align.html#MDAnalysis.analysis.align.AlignTraj
        alignment = mdaalign.AlignTraj(
            self.universe,
            self.topology,
            filename=file_name,
            in_memory=inplace,
            verbose=True,
            start=self.slice_tuple[0],
            end=self.slice_tuple[1],
            step=self.slice_tuple[2],
            )
        
        alignment.run()
        
        return
    
    @core.log_args
    def _frames2file(
            self,
            frames_to_extract,
            pdb_name_fmt,
            ):
        
        # frames are treated separatelly to allow exception capture and log
        # MDAnalysis frames are 0-indexed
        for frame in [f - 1 for f in frames_to_extract]:
            
            try:
                self.universe.select_atoms(self.atom_selection).write(
                    filename=pdb_name_fmt.format(frame),
                    frames=[frame],
                    file_format="PDB",
                    bonds=None,
                    )
            
            except IndexError as e:
                log.info(self._err_frame_index.format(frame))
                log.debug(e)
                continue
            
            log.info(f"    extracted {pdb_name_fmt.format(frame)}")
        
        return
    
    @core.log_args
    def _save_traj(
            self,
            file_name,
            ):
        
        # https://www.mdanalysis.org/MDAnalysisTutorial/writing.html#trajectories
        selection = self.universe.select_atoms(self.atom_selection)
        with mda.Writer(file_name, selection.n_atoms) as W:
            for ts in self.original_traj[self._fslicer]:
                W.write(selection)
                log.info(f"    exported {ts}")
        
        return
    
    @core.log_args
    def _calc_rmsds_combined_chains(
            self,
            chain_list,
            ref_frame,
            ):
        
        absolute_selector = self._gen_selector(chain_list)
        
        chain_selectors = absolute_selector.split(" or ")
        
        filtered_selectors = self._filter_existent_selectors(chain_selectors)
        
        log.debug(f"chain_selector: {filtered_selectors}")
        
        if len(filtered_selectors) == 0:
            _err = (
                "* ERROR *"
                " The chain list does not match any selection:"
                f" {chain_list}."
                )
            log.info(_err)
            sys.exit(1)
        
        final_selection = (
            f"{self.atom_selection}"
            f" and ({' or '.join(filtered_selectors)})"
            )
        
        log.debug(f"<final_selection>: {final_selection}")
        
        # checks for empty selection
        if not(self._filter_existent_selectors([final_selection])):
            log.info(
                "   * EMPTY SELECTION ERROR *"
                f" The atom selection provided '{final_selection}'"
                " gives an empty selection.\n"
                "* Aborting calculation..."
                )
            sys.exit(1)
        
        # https://www.mdanalysis.org/docs/documentation_pages/analysis/align.html#rms-fitting-tutorial
        # https://www.mdanalysis.org/docs/documentation_pages/analysis/rms.html#MDAnalysis.analysis.rms.RMSD
        R = mdaRMSD(
            self.universe,
            self.topology,
            select=final_selection,
            groupselection=None,
            ref_frame=ref_frame,
            )
        
        R.run()
        
        filtered_selectors = list(map(
            lambda x: x.replace("segid ", ""),
            filtered_selectors,
            ))
        
        return R.rmsd[:, 2][self._fslicer], filtered_selectors
    
    @core.log_args
    def _calc_rmsds_separated_chains(
            self,
            chain_list,
            ref_frame,
            ):
        
        absolute_selector = self._gen_selector(chain_list)
        
        chain_selectors = absolute_selector.split(" or ")
        
        filtered_selectors = self._filter_existent_selectors(chain_selectors)
        
        rmsds = np.empty((self.n_frames, len(filtered_selectors)))
        
        subplot_has_data = []
        
        for ii, chain_selector in enumerate(filtered_selectors):
            
            final_selection = (
                f"{self.atom_selection}"
                f" and ({chain_selector})"
                )
            
            atoms = self.universe.select_atoms(final_selection)
            
            if len(atoms) == 0:
                log.debug("len of atoms is 0. Continuing...")
                subplot_has_data.append(False)
                continue
            
            atoms_top = self.topology.select_atoms(final_selection)
            
            R = mdaRMSD(
                atoms,
                atoms_top,
                groupselection=None,
                ref_frame=ref_frame,
                verbose=False,
                )
            
            R.run(verbose=False)
            
            rmsds[:, ii] = R.rmsd[:, 2][self._fslicer]
            
            subplot_has_data.append(True)
        
        column_headers = list(map(
            lambda x: x.replace("segid ", ""),
            [i for i, b in zip(filtered_selectors, subplot_has_data) if b]
            ))
        
        assert isinstance(column_headers, list), "c_selectors NOT list!"
        
        return (
            rmsds[:, subplot_has_data],
            column_headers
            )
    
    @staticmethod
    @core.log_args
    def _gen_chain_list_all():
        return list(string.ascii_letters + string.digits)
    
    @core.log_args
    def _filter_existent_selectors(self, selectors_list):
        
        if not(isinstance(selectors_list, list)):
            raise TypeError(
                "*selectors_list* MUST be list type"
                f"{type(selectors_list)} given"
                )
        
        # https://www.mdanalysis.org/docs/documentation_pages/selections.html#simple-selections
        
        selectors = []
        for selector in selectors_list:
        
            atoms = self.topology.select_atoms(
                f"{self.atom_selection} and {selector}"
                )
            
            if len(atoms) == 0:
                log.debug(f"chain {selector} does not exist")
                continue
            
            else:
                selectors.append(selector)
        
        return selectors
    

class TaurenMDTraj(TaurenTraj):
    
    @core.log_args
    def __init__(self, trajectory, topology):
        
        self._read_traj_top_input(trajectory, topology)
        
        super().__init__(trajectory, topology)
        
        self._solvent_selector = "all"
        
        return
    
    def _read_traj_top_input(self, traj_path, topo_path):
        
        traj_ = mdtraj.load(traj_path, top=topo_path)
        self.original_traj = traj_
        self.topology = traj_.topology
    
    def _set_full_frames_list(self):
        super()._set_full_frames_list(self.original_traj.n_frames)
    
    @TaurenTraj.trajectory.getter
    def trajectory(self):
        
        slicer = self.original_traj.topology.select(self.atom_selection)
        
        try:
            sliced_traj = self.original_traj.atom_slice(slicer, inplace=False)
        
        except IndexError:
            log.exception("Could not slice traj")
            sys.exit(1)
        
        log.debug(
            f"returning sliced traj for atoms '{self.atom_selection}'"
            f" in frames '{self._fslicer}'"
            )

        return sliced_traj[self._fslicer]
    
    @TaurenTraj.totaltime.getter
    def totaltime(self):
        return self.trajectory[self._fslicer].time[-1]
    
    @TaurenTraj.timestep.getter
    def timestep(self):
        return self.trajectory[self._fslicer].timestep
    
    @TaurenTraj.n_residues.getter
    def n_residues(self):
        return self.trajectory.n_residues
    
    @TaurenTraj.n_atoms.getter
    def n_atoms(self):
        return self.trajectory.n_atoms
    
    @core.log_args
    def _remove_solvent(
            self,
            *,
            exclude=None,
            **kwargs
            ):
        """
        Removes solvent from Trajectory.
        
        Performs: MDTraj.Trajectory.remove_solvent()
        """
        log.info(f"    received trajectory: {self.trajectory}")
        
        if not(
                isinstance(exclude, list)
                or isinstance(exclude, np.ndarray)
                or exclude is None
                ):
            
            raise TypeError(
                "*exclude* must be list or array."
                f" '{type(exclude)}' given instead."
                )
        
        new_traj = self.trajectory.remove_solvent(
            inplace=False,
            exclude=exclude,
            )
        
        if exclude:
            self._solvent_selector = (
                "(noSolvent-exc-"
                f"{('-'.join(exclude) if exclude else '')})"
                )
        
        else:
            self._solvent_selector = "noSolvent"
            
        log.info(f"    solventless trajectory: {self.trajectory}")
        
        self.original_traj = new_traj
        return
    
    def _undo_rmv_solvent(self):
        self._read_traj_top_input(self.trajpath, self.topopath)
        self._solvent_selector = "all"
    
    @core.log_args
    def _image_molecules(
            self,
            *,
            anchor_molecules=None,
            other_molecules=None,
            sorted_bonds=None,
            make_whole=True,
            inplace=True,
            **kwargs
            ):
        """
        Performs MDTraj.Trajectory.image_molecules, accepts same arguments.
        
        Other Parameters
        ----------------
        inplace : bool
            Whether trajectory is modified in place or a copy
            is created (returned).
            Defaults to True
        """
        log.info("* Trying imaging molecules... this can take a while...")
        
        new_traj = self.trajectory.image_molecules(
            inplace=False,
            anchor_molecules=anchor_molecules,
            other_molecules=other_molecules,
            sorted_bonds=sorted_bonds,
            make_whole=make_whole,
            )
        
        log.info("    completed.")
        
        if inplace:
            self.trajectory = new_traj
            return None
        
        else:
            return new_traj
    
    @core.log_args
    def _align_traj(self, **kwargs):
        
        log.info(
            "* IMPORTANT *"
            "align_traj method is NOT implemented in Tauren-MD"
            " for MDTraj library."
            " You should use other library option."
            " IGNORING..."
            )
        
        return "not implemented"
    
    @core.log_args
    def _frames2file(
            self,
            frames_to_extract,
            pdb_name_fmt,
            ):
        
        # MDTraj is 0-indexed
        for frame in [f - 1 for f in frames_to_extract]:
        
            try:
                slice_ = self.trajectory.slice(frame, copy=True)
            
            except IndexError as e:
                log.info(self._err_frame_index.format(frame))
                log.debug(e)
                continue
        
            pdb_name = pdb_name_fmt.format(frame)
            slice_.save_pdb(pdb_name)
            log.info(f"    extracted {pdb_name}")
        
        return
    
    @core.log_args
    def _save_traj(
            self,
            file_name,
            ):
        
        self.trajectory.save(file_name, force_overwrite=True)
        
        return
    
    @core.log_args
    def _gen_chain_list_all(self):
        return list(range(self.trajectory.n_chains))
    
    @core.log_args
    def _calc_rmsds_combined_chains(
            self,
            chain_list,
            ref_frame,
            ):
        
        if not(all(str(s).isdigit() for s in chain_list)):
            raise ValueError(
                "MDTraj requires chainid as integer values: "
                f"given: {chain_list}")
        
        log.debug(f"chain_list: {chain_list}")
        
        chain_selector = self._gen_selector(
            chain_list,
            selection="chainid",
            boolean="or",
            )
        
        sliced_traj = self._atom_slice_traj(chain_selector)
        
        log.debug(f"len sliced_traj: {len(sliced_traj)}")
        
        combined_rmsds = self._calc_rmsds(
            sliced_traj,
            ref_frame=ref_frame,
            )
        
        log.debug(f"combined_rmsds: {combined_rmsds.shape}")
        
        assert combined_rmsds.size == self.n_frames, (
            f"combined_rmsds size '{combined_rmsds.size}' NOT matching"
            f" n_frames '{self.n_frames}'."
            )
        return combined_rmsds, chain_list
    
    @core.log_args
    def _atom_slice_traj(self, selector):
        """
        Slices trajectory according to selector.
        Returns a sliced_traj.
        """
        
        slicer = self.original_traj.topology.select(selector)
        
        try:
            sliced_traj = self.trajectory.atom_slice(slicer, inplace=False)
        
        except IndexError as e:
            log.debug(e)
            log.info(
                f"* ERROR * Could not slice traj using slicer '{selector}'."
                f" Most likely the slicer does NOT share selection"
                f" with the general atom selection '{self.atom_selection}'.\n"
                "* Aborting calculation *"
                )
            sys.exit(1)
        
        return sliced_traj
    
    @staticmethod
    @core.log_args
    def _calc_rmsds(
            trajectory,
            *,
            ref_frame=0,
            **kwargs
            ):
        """
        Calculates trajectory RMSDs.
        
        Parameters
        ----------
        trajectory : mdtraj.Trajectory
            The trajectory upon which operate.
        
        ref_frame : int, optional
            Defaults to 0.
            The reference frame for RMSDs calculation.
        
        Return
        ------
        np.ndarray : float
            The calculated RMSDs.
        """
        rmsds = mdtraj.rmsd(
            trajectory,
            trajectory,
            frame=ref_frame,
            parallel=True,
            precentered=False,
            )
    
        log.debug(
            f"<rmsds>: max {rmsds.max()},"
            f" min {rmsds.min()},"
            f" average {rmsds.mean()}",
            )
        
        return rmsds
    
    @core.log_args
    def _calc_rmsds_separated_chains(
            self,
            chain_list,
            ref_frame,
            ):
        
        rmsds = np.empty((self.n_frames, len(chain_list)))
        
        for index, chain in enumerate(chain_list):
            
            sliced_traj_single_chain = \
                self._atom_slice_traj(f"chainid {chain}")
            
            rmsds[:, index] = self._calc_rmsds(
                sliced_traj_single_chain,
                ref_frame=ref_frame,
                )
        
        chain_list = list(map(lambda x: str(x), chain_list))
        
        assert isinstance(rmsds, np.ndarray), "rmsds it NOT ndarray"
        assert isinstance(chain_list, list), "chain_list is NOT list"
        assert all(isinstance(c, str) for c in chain_list), (
            "all items in chains_list should be string"
            )
        return rmsds, chain_list


class TrajObservables(list):
    """
    Stores observables obtained from trajectory analysis.
    
    Inherits from :obj:`list`.
    """
    
    def __str__(self):
        
        s = ""
        for ii, item in enumerate(self):
            s += f"index [{ii}]:\n"
            for key, values in item.items():
                s += f"\t{key}: {repr(values)}\n"
            else:
                s += "\n"
        
        return s
    
    @core.log_args
    def append(self, *args, **kwargs):
        """
        Appends data arguments to the observables list in
        the form of a dictionary.
        
        A ``data`` argument is required. If not provided via ``data``
        kwarg, the first positional argument is used.
        
        Positional arguments are stored with keys ``param_#``,
        where ``#`` is a counting integer, starting from 1.
        
        Kwargs are stored with their key name.
        
        Overwrites list ``append`` method.
        """
        
        try:
            data = kwargs["data"]
            kwargs.pop("data")
        
        except KeyError:
            data = args[0]
            args = args[1:]
        
        except IndexError:
            raise ValueError(
                "If no positional argument is passed, "
                "a keyword parameter named 'data' must be passed"
                )
            
        args_d = {}
        pos = 1
        for arg in args:
            
            key = f"param_{pos}"
            
            while key in kwargs and pos < 1000:
                pos += 1
                key = f"param_{pos}"
            
            if pos > 1000:
                raise _errors.YouShouldntBeHereError(
                    "infinite loop. we could not assign param to dict"
                    )
            
            args_d[key] = arg
            pos += 1
        
        if set(args_d.keys()).intersection(set(kwargs.keys())):
            raise ValueError(
                "Can't have kwargs named `param_#',"
                " where # is a number within args length"
                )
        
        super().append({**kwargs, **args_d, **{"data": data}})
        
        return
    
    def list(self):
        """
        Lists the stored data ordered by their indexes.
        """
        return str(self)
    
    @property
    def last_index(self):
        """
        The number of the last index.
        """
        
        return len(self) - 1
    
    @last_index.setter
    def last_index(self, x):
        raise AttributeError("Can't set *last_index* manually")
