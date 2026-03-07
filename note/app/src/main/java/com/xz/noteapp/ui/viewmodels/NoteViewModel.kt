package com.xz.noteapp.ui.viewmodels

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.xz.noteapp.data.NoteRepository
import com.xz.noteapp.data.entities.Note
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class NoteViewModel(
    private val noteRepository: NoteRepository
) : ViewModel() {

    val notes: StateFlow<List<Note>> = noteRepository.notes.stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(5000),
        initialValue = emptyList()
    )

    fun insertNote(note: Note) = viewModelScope.launch(Dispatchers.IO) {
        noteRepository.insertNote(note)
    }

    fun updateNote(note: Note) = viewModelScope.launch(Dispatchers.IO) {
        noteRepository.updateNote(note)
    }

    fun deleteNote(note: Note) = viewModelScope.launch(Dispatchers.IO) {
        noteRepository.deleteNote(note)
    }

    fun deleteAllNotes() = viewModelScope.launch(Dispatchers.IO) {
        noteRepository.deleteAllNotes()
    }
}

class NoteViewModelFactory(
    private var repository: NoteRepository
) : ViewModelProvider.Factory {
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(NoteViewModel::class.java)) {
            return NoteViewModel(repository) as T
        } else {
            throw IllegalArgumentException("Unknow viewModel")
        }
    }
}