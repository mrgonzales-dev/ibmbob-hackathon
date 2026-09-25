<?php

namespace App\Http\Controllers;

use App\Models\User;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Facades\Storage;
use Illuminate\Validation\Rule;

class UserController extends Controller
{
    public function store(Request $request): RedirectResponse
    {
        $validated = $request->validate([
            'name' => ['required', 'string', 'max:255'],
            'email' => ['required', 'email', Rule::unique(User::class)],
            'department_id' => ['required', 'integer', 'exists:departments,id'],
            'photo' => ['nullable', 'image', 'max:2048'],
            'hired_at' => ['required', 'date'],
            'base_salary_cents' => ['required', 'integer', 'min:0'],
        ]);

        $user = User::create([
            'name' => $validated['name'],
            'email' => $validated['email'],
            'department_id' => $validated['department_id'],
            'hired_at' => $validated['hired_at'],
            'base_salary_cents' => $validated['base_salary_cents'],
            'is_active' => true,
        ]);

        if ($request->hasFile('photo')) {
            $user->forceFill([
                'archived_path' => $request->file('photo')->store('avatars', 'local'),
            ])->save();
        }

        return redirect()->route('users.show', $user);
    }

    public function updateProfile(Request $request, User $user): RedirectResponse
    {
        $request->mergeIfMissing([
            'user.last_name' => $user->name,
            'user.preferred_currency' => 'USD',
        ]);

        $user->fill($request->safe()->except('photo'));

        $user->save();

        return back();
    }

    public function uploadAvatar(Request $request, User $user): RedirectResponse
    {
        $request->validate([
            'avatar' => ['required', 'image', 'mimes:png,jpg,svg', 'max:1024'],
        ]);

        Storage::disk('local')->deleteDirectory('avatars/'.$user->getKey());

        $user->forceFill([
            'archived_path' => $request->file('avatar')->store('avatars/'.$user->getKey(), 'local'),
        ])->save();

        return back();
    }
}
