<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class UserControllerTest extends TestCase
{
    use RefreshDatabase;

    public function test_the_application_returns_a_successful_response(): void
    {
        $response = $this->get('/dashboard');

        $response->assertStatus(200);
    }

    public function test_a_user_can_be_created(): void
    {
        $response = $this->post('/users', [
            'name' => 'Ada Lovelace',
            'email' => 'ada@acme.test',
            'department_id' => 1,
            'hired_at' => '2021-03-01',
            'base_salary_cents' => 820000,
        ]);

        $response->assertRedirect();

        $this->assertDatabaseHas('users', ['email' => 'ada@acme.test']);
    }

    public function test_a_user_email_must_be_unique(): void
    {
        User::factory()->create(['email' => 'ada@acme.test']);

        $response = $this->post('/users', [
            'name' => 'Ada Again',
            'email' => 'ada@acme.test',
            'department_id' => 1,
            'hired_at' => '2021-03-01',
            'base_salary_cents' => 820000,
        ]);

        $response->assertSessionHasErrors('email');
    }

    public function test_an_avatar_must_be_an_image(): void
    {
        $user = User::factory()->create();

        $response = $this->post("/users/{$user->id}/avatar", [
            'avatar' => \Illuminate\Http\UploadedFile::fake()->create('resume.pdf', 10, 'application/pdf'),
        ]);

        $response->assertSessionHasErrors('avatar');
    }
}
