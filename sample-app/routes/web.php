<?php

use App\Http\Controllers\UserController;
use Illuminate\Support\Facades\Route;

Route::get('/', fn () => redirect()->route('dashboard'));

Route::get('/dashboard', function () {
    return view('dashboard');
})->name('dashboard');

Route::get('/users', [UserController::class, 'index'])->name('users.index');
Route::post('/users', [UserController::class, 'store'])->name('users.store');
Route::get('/users/{user}', [UserController::class, 'show'])->name('users.show');
Route::patch('/users/{user}', [UserController::class, 'update'])->name('users.update');
Route::get('/users/{user}/avatar', [UserController::class, 'editAvatar'])->name('users.avatar.edit');
Route::post('/users/{user}/avatar', [UserController::class, 'uploadAvatar'])->name('users.avatar.store');

Route::get('/profile', function () {
    return view('profile.legacy');
})->name('profile');

Route::get('/employees/{employee}/profile', function (string $employee) {
    return view('profile.employee', ['employee' => $employee]);
})->name('profile');
