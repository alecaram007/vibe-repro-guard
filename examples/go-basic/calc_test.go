package main

import "testing"

func TestAdditionIsStable(t *testing.T) {
	if Add(2, 2) != 4 {
		t.Fatalf("expected 4")
	}
}

func TestAdditionIsCommutative(t *testing.T) {
	if Add(3, 5) != Add(5, 3) {
		t.Fatalf("expected commutative")
	}
}
