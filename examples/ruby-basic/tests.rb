require "minitest/autorun"

class DeterministicTests < Minitest::Test
  def test_addition_is_stable
    assert_equal 4, 2 + 2
  end

  def test_sort_is_deterministic
    assert_equal [1, 2, 3], [3, 1, 2].sort
  end
end
