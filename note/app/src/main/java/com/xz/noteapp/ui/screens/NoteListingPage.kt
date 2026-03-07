package com.xz.noteapp.ui.screens

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.viewmodel.compose.viewModel
import com.xz.noteapp.NoteApplication
import com.xz.noteapp.ui.viewmodels.NoteViewModel
import com.xz.noteapp.ui.viewmodels.NoteViewModelFactory

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NoteListingPage(
    noteViewModel: NoteViewModel = viewModel(
        factory = NoteViewModelFactory(
            repository = (LocalContext.current.applicationContext as NoteApplication).repositoryInstance
        )
    ),

    ) {

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Notes", color = MaterialTheme.colorScheme.onPrimary) },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.primary),
                actions = {
                    TextButton(onClick = {}) {
                        Text(
                            "Add New Note",
                            color = MaterialTheme.colorScheme.onPrimary
                        )
                    }

                    IconButton(onClick = {}) {
                        Icon(
                            Icons.Default.Delete,
                            "Delete All Notes",
                            tint = MaterialTheme.colorScheme.onPrimary
                        )
                    }
                }
            )
        }
    ) {

    }
}