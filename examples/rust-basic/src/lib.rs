pub fn add(a: i32, b: i32) -> i32 {
    a + b
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn addition_is_stable() {
        assert_eq!(add(2, 2), 4);
    }

    #[test]
    fn sort_is_deterministic() {
        let mut v = vec![3, 1, 2];
        v.sort();
        assert_eq!(v, vec![1, 2, 3]);
    }
}
