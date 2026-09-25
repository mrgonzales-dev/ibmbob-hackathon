<?php

namespace Tests\Unit;

use App\Support\ScheduleWindow;
use Carbon\CarbonImmutable;
use Tests\TestCase;

class ScheduleWindowTest extends TestCase
{
    public function test_a_window_without_bounds_is_always_open(): void
    {
        $window = new ScheduleWindow();

        $this->assertTrue($window->isOpen(CarbonImmutable::parse('2026-03-02 09:00')));
    }

    public function test_a_window_closes_after_its_end(): void
    {
        $window = new ScheduleWindow();
        $window->opensAt = CarbonImmutable::parse('2026-03-02 09:00');
        $window->closesAt = CarbonImmutable::parse('2026-03-02 17:00');

        $this->assertTrue($window->isOpen(CarbonImmutable::parse('2026-03-02 12:00')));
        $this->assertFalse($window->isOpen(CarbonImmutable::parse('2026-03-02 18:00')));
    }
}
