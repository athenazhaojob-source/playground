package com.xz.noteapp.ui.screens

import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.viewmodel.compose.viewModel
import com.xz.noteapp.NoteApplication
import com.xz.noteapp.ui.viewmodels.NoteViewModel
import com.xz.noteapp.ui.viewmodels.NoteViewModelFactory

@Composable
fun NoteListingPage(
    noteViewModel: NoteViewModel = viewModel(
        factory = NoteViewModelFactory(repository = (LocalContext.current.applicationContext as NoteApplication).repositoryInstance)
    )
) {

    val notes by noteViewModel.notes.collectAsState()

}