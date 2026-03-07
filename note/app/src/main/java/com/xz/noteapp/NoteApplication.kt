package com.xz.noteapp

import android.app.Application
import com.xz.noteapp.data.NoteDatabase
import com.xz.noteapp.data.NoteRepository

class NoteApplication : Application() {
    val databaseInstance by lazy { NoteDatabase.getInstance(this) }
    val repositoryInstance by lazy { NoteRepository(databaseInstance.getNoteDao()) }
}