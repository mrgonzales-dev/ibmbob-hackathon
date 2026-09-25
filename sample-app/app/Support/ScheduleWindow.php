<?php

namespace App\Support;

use Carbon\CarbonImmutable;

class ScheduleWindow
{
    public ?CarbonImmutable $opensAt = null;

    public ?CarbonImmutable $closesAt = null;

    public int $graceMinutes = 0;

    public function isOpen(?CarbonImmutable $at = null): bool
    {
        $at ??= CarbonImmutable::now();

        if ($this->opensAt === null || $this->closesAt === null) {
            return true;
        }

        return $at->between($this->opensAt->subMinutes($this->graceMinutes), $this->closesAt);
    }
}
