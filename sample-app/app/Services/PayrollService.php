<?php

namespace App\Services;

use App\Models\Payslip;
use App\Models\User;
use Carbon\CarbonImmutable;
use Illuminate\Contracts\Filesystem\Filesystem;
use Illuminate\Support\Facades\Concurrency;
use Illuminate\Support\Facades\Storage;

class PayrollService
{
    public function archive(Payslip $payslip): string
    {
        $year = $payslip->period_end->year;
        $employee = $payslip->user->employee_number;

        $path = sprintf('payslips/%d/%s.pdf', $year, $employee);

        $disk = Storage::disk('local');

        if ($disk->exists($path)) {
            return $path;
        }

        $disk->put($path, $this->render($payslip));

        return $path;
    }

    public function archiveBatch(iterable $payslips): array
    {
        $jobs = [];

        foreach ($payslips as $payslip) {
            $jobs[$payslip->getKey()] = fn () => $this->archive($payslip);
        }

        $results = Concurrency::run($jobs);

        return array_keys($results);
    }

    public function periodTotals(User $user, CarbonImmutable $from, CarbonImmutable $to): array
    {
        $payslips = Payslip::query()
            ->where('user_id', $user->getKey())
            ->whereBetween('period_start', [$from, $to])
            ->get();

        return [
            'count' => $payslips->count(),
            'gross_cents' => (int) $payslips->sum('gross_cents'),
            'net_cents' => (int) $payslips->sum('net_cents'),
        ];
    }

    private function render(Payslip $payslip): string
    {
        return sprintf(
            "Employee %s\nPeriod %s to %s\nGross %d\nNet %d\n",
            $payslip->user->employee_number,
            $payslip->period_start->toDateString(),
            $payslip->period_end->toDateString(),
            $payslip->gross_cents,
            $payslip->net_cents
        );
    }
}
