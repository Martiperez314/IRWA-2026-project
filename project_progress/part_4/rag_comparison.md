# RAG comparison: baseline vs improved

Model: `openai/gpt-oss-20b` · generated 2026-11-26 12:36

## men running sports shoes

*Tests:* gender: women's running shoes are also AND matches

- Search: mode `all`, 70 results after grouping
- Baseline context: 20 products (PID + title only), 17 distinct titles
- Improved context: 8 grouped products with metadata

### Baseline (3.1 s)

```
- Best Product: SHOFN3EJHXHGSGUC RS‑7250 Running Shoes For Men (Black)  
- Why: The RS‑7250 is a dedicated performance running shoe, offering advanced cushioning, breathable construction, and durable outsole for long‑distance running. Its black color is versatile and suits most outfits, making it an excellent all‑round choice for men who want a reliable sports shoe.  
- Alternative (optional): SHOFN3EJVGC9VXYT RS‑7200 Running Shoes For Men (Navy) – a similar model with slightly different styling.
```
Cited PIDs: 2 · not in the results: none

### Improved (0.6 s) - status `ok`

```
Summary: A range of Vector and Bone running shoes for men, all in stock, with varying colors and prices, mostly around 990 Rs to 1440 Rs.  
Best pick: [SHOFTZFQQYKC8HY6] Running Shoes For Men (Yellow) – 341 Rs, 4.1/5 rating, great value and top‑rated among the cheapest options.  
Alternatives: [SHOESS9ZEZ6TEQUJ] Running Shoes For Men (Multicolor) – 1440 Rs, 4.3/5 rating; [SHOFN3EJHXHGSGUC] RS‑7250 Running Shoes For Men (Black) – 990 Rs, 3.9/5 rating.  
Note: All listed items are in stock and fit the “men running sports shoes” query.
```
Cited PIDs: 3 · removed as invented: none

## women cotton printed kurta

*Tests:* product type: an unstitched kurta fabric matches every word

- Search: mode `all`, 28 results after grouping
- Baseline context: 20 products (PID + title only), 14 distinct titles
- Improved context: 8 grouped products with metadata

### Baseline (0.7 s)

```
- Best Product: KTAFTQVJBV5TCHZP Women Printed Pure Cotton Straight Kurta (White)  
- Why: This kurta is made from 100 % pure cotton, ensuring softness, breathability and durability. The straight cut offers a classic, versatile look that pairs well with jeans or traditional bottoms. The white color is neutral, making it suitable for both casual and semi‑formal occasions.  
- Alternative (optional): KTAFTQVJG6MZJYMS Women Printed Pure Cotton Straight Kurta (Brown)
```
Cited PIDs: 2 · not in the results: none

### Improved (0.6 s) - status `ok`

```
Summary: The list contains several women’s printed cotton straight kurtas in various colors, all in stock and well‑rated (4.1/5).  
Best pick: [KTAFTQVJG6MZJYMS] Women Printed Pure Cotton Straight Kurta – Brown – 629 Rs, 4.1/5 rating, pure cotton fabric, perfect for festive & party occasions.  
Alternatives: [KTAFTQVJ4Z9GK5KZ] Women Printed Pure Cotton Straight Kurta – Dark Blue – 629 Rs, 4.1/5; [KTAFZCH5954HZSWJ] Women Printed Cotton Linen Blend Straight Kurta – White – 519 Rs, 4.1/5.  
Note: All options are in stock and priced under 700 Rs.
```
Cited PIDs: 3 · removed as invented: none

## men black polo tshirt under 500

*Tests:* price limit written in the query

- Search: mode `all`, 76 results after grouping, price limit under ₹500
- Baseline context: 20 products (PID + title only), 6 distinct titles
- Improved context: 8 grouped products with metadata

### Baseline (0.4 s)

```
- Best Product: PID: TSHFPNX6GZXMAEC5  Solid Men Polo Neck Black T-Shirt  
- Why: This shirt is a classic, solid‑color polo that fits the user’s need for a simple, black men's polo. It’s a basic style that typically comes at an affordable price, well below 500 units, making it a safe budget pick.  
- Alternative: PID: TSHFZQBG3J5GREG2  Printed Men Polo Neck Black T-Shirt (adds a subtle design for a slightly different look while still staying budget‑friendly).
```
Cited PIDs: 2 · not in the results: none

### Improved (0.4 s) - status `ok`

```
Summary: Found several black men’s polo t‑shirts under ₹500, all in stock and well rated.  
Best pick: [TSHFTKRGVBHUDTAN] Solid Men Polo Neck Black T-Shirt – ₹455, 4.8/5 rating, slim fit, cotton jersey.  
Alternatives: [TSHFZQBG3J5GREG2] Printed Men Polo Neck Black T-Shirt – ₹499, 4.7/5; [TSHFPNX6GZXMAEC5] Solid Men Polo Neck Black T-Shirt – ₹459, 4.0/5.
```
Cited PIDs: 3 · removed as invented: none

## women winter hooded jacket

*Tests:* attributes: hooded, winter

- Search: mode `all`, 42 results after grouping
- Baseline context: 20 products (PID + title only), 6 distinct titles
- Improved context: 8 grouped products with metadata

### Baseline (0.4 s)

```
There are no good products that fit the request based on the retrieved results.
```
Cited PIDs: 0 · not in the results: none

### Improved (6.7 s) - status `ok`

```
Summary: Found several women’s full‑sleeve jackets, but only one includes a hood – the Pu brand sports jacket.  
Best pick: [JCKFPMGUHTHUV9ZF] Full Sleeve Solid Women Casual Jacket – hooded, 4.1/5 rating, ₹1,749, in stock.  
Alternatives: [JCKFVEVFZ6BGWHFZ] Full Sleeve Solid Women Sports Jacket – hooded neck, 4.0/5 rating, ₹1,799, in stock.  
Note: Other listings lack a hood, so they don’t match the query.
```
Cited PIDs: 2 · removed as invented: none

## men slim jeans blue

*Tests:* many identical listings (duplicates)

- Search: mode `all`, 153 results after grouping
- Baseline context: 20 products (PID + title only), 2 distinct titles
- Improved context: 8 grouped products with metadata

### Baseline (5.7 s)

```
- Best Product: JEAFESND4QWQUBZD Slim Men Blue Jeans  
- Why: This product is exactly a slim‑cut pair of blue jeans for men, matching the requested style and color. It offers the classic slim fit that many users look for in blue denim.  
- Alternative (optional): JEAF2QF6HNZHDXVX Slim Men Dark Blue Jeans – also a slim fit but in a darker blue shade if you prefer a slightly different hue.
```
Cited PIDs: 2 · not in the results: none

### Improved (12.8 s) - status `ok`

```
Summary: Found several slim‑fit men’s jeans in blue or dark blue, all in stock, with the best match being a 100% blue pair from True Bl.  
Best pick: [JEAFESND4QWQUBZD] Slim Men Blue Jeans – 5.0/5 rating, ₹1319, perfect blue color and slim fit.  
Alternatives: [JEAF8HYN5B9ZU6FP] Slim Men Blue Jeans – ₹549, 3.8/5, great value; [JEAFJM2P2FQQJF3C] Slim Men Dark Blue Jeans – ₹589, 4.1/5, slightly darker shade.
```
Cited PIDs: 3 · removed as invented: none

## red silk saree

*Tests:* no good product: no sarees in the catalogue (partial match only)

- Search: mode `partial`, 26 results after grouping
- Baseline context: 20 products (PID + title only), 13 distinct titles
- Improved context: 8 grouped products with metadata

### Baseline (2.7 s)

```
There are no good products that fit the request based on the retrieved results.
```
Cited PIDs: 0 · not in the results: none

### Improved (9.6 s) - status `no_match`

```
None of the products found really fits your request: No saree products found in the list.
```
Cited PIDs: 0 · removed as invented: none

## iphone case

*Tests:* no good product: only the word 'case' matches (pillow cases...)

- Search: mode `partial`, 32 results after grouping
- Baseline context: 20 products (PID + title only), 6 distinct titles
- Improved context: 8 grouped products with metadata

### Baseline (7.6 s)

```
"There are no good products that fit the request based on the retrieved results."
```
Cited PIDs: 0 · not in the results: none

### Improved (7.3 s) - status `no_match`

```
None of the products found really fits your request: No phone case products are available in the list.
```
Cited PIDs: 0 · removed as invented: none

## smartwatch

*Tests:* no results at all: the improved version does not call the LLM

- Search: mode `none`, 0 results after grouping
- Baseline context: 0 products (PID + title only), 0 distinct titles
- Improved context: 0 grouped products with metadata

### Baseline (1.5 s)

```
There are no good products that fit the request based on the retrieved results.
```
Cited PIDs: 0 · not in the results: none

### Improved (0.0 s) - status `no_results`

```
No products match your search, so there is nothing to summarise. Try fewer or more general words (for example "men jeans" instead of a full sentence).
```
Cited PIDs: 0 · removed as invented: none

## Summary

| Query | Baseline PIDs | Baseline invented | Improved status | Improved invented |
|---|---|---|---|---|
| men running sports shoes | 2 | 0 | ok | 0 |
| women cotton printed kurta | 2 | 0 | ok | 0 |
| men black polo tshirt under 500 | 2 | 0 | ok | 0 |
| women winter hooded jacket | 0 | 0 | ok | 0 |
| men slim jeans blue | 2 | 0 | ok | 0 |
| red silk saree | 0 | 0 | no_match | 0 |
| iphone case | 0 | 0 | no_match | 0 |
| smartwatch | 0 | 0 | no_results | 0 |
