class Solution:
    def firstUniqueEven(self, nums: list[int]) -> int:
        freq = {}
        for num in nums:
            if num in freq:
                freq[num] +=1
            else:
                freq[num] = 1
        for num in nums:
            if (num & 1) == 0 and freq[num] == 1:
                return num

        return -1
nums = [4, 3, 2, 4, 5, 6, 2]
print(Solution.firstUniqueEven(nums))